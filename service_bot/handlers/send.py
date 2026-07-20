from aiogram import Router, F
from aiogram.types import Message

from service_bot.worker import StreamChat


stream_chatbot = StreamChat()
send_router = Router()


@send_router.message(F.text)
async def stream_response(message: Message):
    stream = await stream_chatbot()