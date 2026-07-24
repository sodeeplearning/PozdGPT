from aiogram import Router, F
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Message

import asyncio
import asyncpg
from loguru import logger

from commenter import commenter


router = Router()


@router.message(F.text, F.is_automatic_forward == True)
async def write_comment(message: Message, db: asyncpg.Pool):
    row = await db.fetchrow(
        """
        WITH ch AS (SELECT owner_user_id
                    FROM channels
                    WHERE group_id = $1
                      AND active = TRUE)
        UPDATE users
        SET balance = balance - 1 FROM ch
        WHERE users.tg_user_id = ch.owner_user_id
          AND users.balance
            > 0
            RETURNING users.tg_user_id
        """,
        message.chat.id,
    )
    if not row:
        return

    generated_comment = await commenter(message.text)

    try:
        await message.reply(generated_comment)
    except TelegramRetryAfter as e:
        logger.warning(
            f"Failed to write comment due to flood control. Sleeping {e.retry_after} seconds")
        await asyncio.sleep(e.retry_after)
        await message.reply(generated_comment)
