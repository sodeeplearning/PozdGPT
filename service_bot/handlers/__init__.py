import asyncpg

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from . import admin, comment, hooks, manage, payment, dialog

from config import Payment


router = Router()

router.include_routers(
    admin.router,
    comment.router,
    hooks.router,
    manage.router,
    payment.router,
    dialog.router,
)


@router.message(CommandStart())
async def startup_event(message: Message, db: asyncpg.Pool):
    await message.reply("PozdGPT вас приветствует!")

    if message.from_user:
        await db.execute("""
            INSERT INTO users (tg_user_id, username, balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_user_id) DO NOTHING""",
            message.from_user.id, message.from_user.username, Payment.default_user_messages,
        )
