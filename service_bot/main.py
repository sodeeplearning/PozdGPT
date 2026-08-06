from aiogram import Bot, Dispatcher
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncpg
from loguru import logger

from handlers import router
from config import TelegramBotParams, Payment


bot = Bot(token=TelegramBotParams.bot_token)

dp = Dispatcher()
dp.include_router(router)


async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_user_id BIGINT PRIMARY KEY,
                username VARCHAR,
                balance INTEGER DEFAULT 100
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                charge_id TEXT PRIMARY KEY,
                tg_user_id BIGINT,
                messages_added INTEGER,
                price FLOAT,
                created_at TIMESTAMPTZ DEFAULT now()
            )""")


async def reset_balances(db: asyncpg.Pool):
    try:
        result = await db.execute(
            "UPDATE users SET balance = $1 WHERE balance < $1",
            Payment.default_user_messages,
        )
        logger.info(f"Balance reset done: {result}")
    except Exception as e:
        logger.error(f"Failed to reset balances: {e}")


def setup_scheduler(db: asyncpg.Pool) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        reset_balances,
        CronTrigger(hour=0, minute=0),
        args=[db],
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler


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
    scheduler = setup_scheduler(pool)

    logger.info("Service setup complete!")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await pool.close()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
