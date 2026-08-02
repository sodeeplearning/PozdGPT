import asyncpg
from loguru import logger

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    LabeledPrice,
    PreCheckoutQuery,
    ChatMemberMember,
    ChatMemberAdministrator,
    ChatMemberOwner,
)
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TelegramBotParams, Payment


router = Router()


class PackageCallbackData(CallbackData, prefix="buy"):
    package_name: str
    messages_amount: int
    price: int


@router.message(Command("monet"))
async def payment_info(message: Message, db: asyncpg.Pool):
    is_subscribed = False
    channel_member = await message.bot.get_chat_member(
        chat_id=TelegramBotParams.telegram_channel_id,
        user_id=message.from_user.id,
    )
    if isinstance(channel_member, (ChatMemberMember, ChatMemberAdministrator, ChatMemberOwner)):
        is_subscribed = True

    result = await db.fetchrow(
        "SELECT balance FROM users WHERE tg_user_id = $1",
        message.from_user.id,
    )
    user_balance = result["balance"]

    kb = InlineKeyboardBuilder()
    for package_name, data in Payment.packages.items():
        messages = int(data["messages_amount"] * (1 + Payment.subscribed_addition_percent / 100 * is_subscribed))
        kb.button(
            text=f"{messages} сообщений за {data["price"]}⭐",
            callback_data=PackageCallbackData(
                package_name=package_name,
                messages_amount=messages,
                price=data["price"],
            ),
        )
    kb.button(
        text="Проверить подписку на канал PozdGPT",
        callback_data="payment_recall",
    )
    kb.adjust(1, 1)

    sample_photo = FSInputFile("docs/images/commentary_sample.png")
    text = f"""
    **PozdGPT — твой главный помощник**

    🤖  PozdGPT может автоматически писать комментарии под вашими постами.
        PozdGPT может отвечать в личных чатах (просто упомяните его)
        PozdGPT может отвечать в ваших группах (также можно просто упомянуть его!)

    ⭐ Осталось сообщений от PozdGPT: **{user_balance}**

    Чтобы подключить комментарии от PozdGPT:
    Добавьте PozdGPT администратором в группу обсуждений (можно без каких-либо разрешений).
    Готово! Теперь PozdGPT сможет оставлять комментарии под новыми постами.

    Если лимит закончится — его можно пополнить ниже.
    (с подпиской на канал https://t.me/pozdgpt на {Payment.subscribed_addition_percent}% больше комментариев!)
    """

    await message.reply_photo(
        photo=sample_photo,
        caption=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "payment_recall")
async def payment_handler_recall(callback: CallbackQuery, db: asyncpg.Pool):
    await payment_info(callback.message.reply_to_message, db)


@router.callback_query(PackageCallbackData.filter())
async def send_invoice(query: CallbackQuery, callback_data: PackageCallbackData):
    package_name = callback_data.package_name
    package_data = Payment.packages[package_name]

    await query.bot.send_invoice(
        chat_id=query.message.chat.id,
        title=f"PozdGPT-комментатор",
        description=f"{package_data["messages_amount"]} комментариев в вашем канале от PozdGPT",
        payload=package_name,
        currency="XTR",
        prices=[LabeledPrice(
            label=f"{package_data["messages_amount"]} комментариев",
            amount=package_data["price"],
        )]
    )
    await query.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_payment(message: Message, db: asyncpg.Pool):
    logger.info("Received payment")
    payload = message.successful_payment.invoice_payload
    data = Payment.packages[payload]
    charge_id = message.successful_payment.telegram_payment_charge_id

    async with db.acquire() as conn:
        async with conn.transaction():
            try:
                await conn.execute(
                    "INSERT INTO transactions (charge_id, tg_user_id, messages_added, price) VALUES ($1, $2, $3, $4)",
                    charge_id, message.from_user.id, data["messages_amount"], data["price"]
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + $1 WHERE tg_user_id = $2",
                    data["messages_amount"], message.from_user.id,
                )
            except asyncpg.UniqueViolationError:
                logger.error(f"UniqueViolationError while transaction process: {charge_id}")
                return

    await message.reply(
        f"Баланс комментариев от PozdGPT пополнен на {data["messages_amount"]} комментариев"
    )
