import asyncio
from aiogram import Bot, Dispatcher

from handlers import router
from config import TelegramBotParams


bot = Bot(token=TelegramBotParams.bot_token)

dp = Dispatcher()
dp.include_router(router)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
