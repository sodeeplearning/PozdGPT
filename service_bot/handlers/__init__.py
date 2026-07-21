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
async def startup_event(message: Message):
    await message.reply("Гойда!")

