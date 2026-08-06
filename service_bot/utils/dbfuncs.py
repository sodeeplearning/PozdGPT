from asyncpg import Pool

from config import Payment


async def add_user(tg_user_id: int, username: str, db: Pool):
    await db.execute("""
        INSERT INTO users (tg_user_id, username, balance)
        VALUES ($1, $2, $3)
        ON CONFLICT (tg_user_id) DO NOTHING""",
        tg_user_id, username, Payment.default_user_messages,
    )
