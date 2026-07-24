from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from memory import memory


router = Router()


@router.message(Command("clear"))
async def clear_chat_history(message: Message):
    memory.clear_history(message.from_user.id)
    await message.reply("PozdGPT забыл о чем с вами говорил!")
