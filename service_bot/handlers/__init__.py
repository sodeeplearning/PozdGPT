from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from . import manage, send


router = Router()

router.include_routers(
    manage.router,
    send.router,
)

@router.message(CommandStart())
async def startup_event(message: Message):
    await message.reply("Гойда!")

