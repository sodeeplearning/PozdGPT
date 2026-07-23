from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

import asyncpg
from loguru import logger


router = Router()


packages = { # package_name: commentaries amount - price in telegram stars
    "package_1000": {"messages_amount": 1000, "price": 1}
}


@router.message(Command("buy"))
async def buy_package(message: Message):
    kb = InlineKeyboardBuilder()
    for package_name, data in packages.items():
        kb.button(
            text=f"{data["messages_amount"]} комментариев за {data["price"]}⭐",
            callback_data=f"buy:{package_name}",
        )
    kb.adjust(1)
    await message.reply("PozdGPT - комментатор", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("buy:"))
async def send_invoice(callback: CallbackQuery):
    package_name = callback.data.split(":", 1)[1]
    package_data = packages[package_name]

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
    data = packages[payload]
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
