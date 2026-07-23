import asyncpg

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from . import comment, hooks, manage, payment, send


router = Router()

router.include_routers(
    comment.router,
    hooks.router,
    manage.router,
    payment.router,
    send.router,
)

@router.message(CommandStart())
async def startup_event(message: Message, db: asyncpg.Pool):
    await message.reply("PozdGPT вас приветствует!")

    await db.execute("""
        INSERT INTO users (tg_user_id, username, balance)
        VALUES ($1, $2, 50)
        ON CONFLICT (tg_user_id) DO NOTHING""",
        message.from_user.id, message.from_user.username,
    )
