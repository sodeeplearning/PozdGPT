import asyncpg
from loguru import logger

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, FSInputFile, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Payment


router = Router()


@router.message(Command("comment"))
async def commentary_info(message: Message, db: asyncpg.Pool):
    result = await db.fetchrow(
        "SELECT balance FROM users WHERE tg_user_id = $1",
        message.from_user.id,
    )
    user_balance = result["balance"]

    kb = InlineKeyboardBuilder()
    for package_name, data in Payment.packages.items():
        kb.button(
            text=f"{data["messages_amount"]} комментариев за {data["price"]}⭐",
            callback_data=f"buy:{package_name}",
        )
    kb.adjust(1)

    sample_photo = FSInputFile("docs/images/commentary_sample.png")
    text = f"""
    **PozdGPT — комментатор**

    🤖 PozdGPT может автоматически писать комментарии под вашими постами.

    ⭐ Осталось комментариев: **{user_balance}**

    Чтобы подключить:
    Добавьте PozdGPT администратором в группу обсуждений (можно без каких-либо разрешений).
    Готово! Теперь PozdGPT сможет оставлять комментарии под новыми постами.

    Если лимит закончится — его можно пополнить ниже.
    """

    await message.reply_photo(
        photo=sample_photo,
        caption=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("buy:"))
async def send_invoice(callback: CallbackQuery):
    package_name = callback.data.split(":", 1)[1]
    package_data = Payment.packages[package_name]

    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"PozdGPT-комментатор",
        description=f"{package_data["messages_amount"]} комментариев в вашем канале от PozdGPT",
        payload=package_name,
        currency="XTR",
        prices=[LabeledPrice(
            label=f"{package_data["messages_amount"]} комментариев",
            amount=package_data["price"],
        )]
    )
    await callback.answer()


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
