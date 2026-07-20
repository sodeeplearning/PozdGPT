import asyncio
from aiogram import Bot, Dispatcher

from config import TelegramBotParams


bot = Bot(token=TelegramBotParams.bot_token)
dp = Dispatcher()


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
