import asyncio
import asyncpg
from aiogram import Bot, Dispatcher
from loguru import logger

from handlers import router
from config import TelegramBotParams


bot = Bot(token=TelegramBotParams.bot_token)

dp = Dispatcher()
dp.include_router(router)


async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_user_id BIGINT PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )""")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id BIGINT PRIMARY KEY,
                group_id BIGINT,
                owner_user_id BIGINT,
                active BOOLEAN DEFAULT TRUE,
                CONSTRAINT fk_channel_owner
                    FOREIGN KEY (owner_user_id)
                    REFERENCES users(tg_user_id)
            )""")


async def main():
    pool = await asyncpg.create_pool(
        host=TelegramBotParams.db_host,
        port=TelegramBotParams.db_port,
        user=TelegramBotParams.db_user,
        password=TelegramBotParams.db_password,
        database=TelegramBotParams.db_name,
        min_size=2,
        max_size=TelegramBotParams.max_pool_connections,
    )
    await init_db(pool)
    dp["db"] = pool

    logger.info("Service setup complete!")

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
