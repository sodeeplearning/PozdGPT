import asyncpg

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from . import admin, comment, hooks, payment, dialog

from utils.dbfuncs import add_user


router = Router()

router.include_routers(
    admin.router,
    comment.router,
    hooks.router,
    payment.router,
    dialog.router,
)


@router.message(CommandStart())
async def startup_event(message: Message, db: asyncpg.Pool):
    await message.reply("PozdGPT вас приветствует!")

    if message.from_user:
        await add_user(message.from_user.id, message.from_user.username, db)
