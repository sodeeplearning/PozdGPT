import asyncpg
from loguru import logger

from aiogram import Router
from aiogram.types import ChatMemberUpdated


router = Router()


@router.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated, db: asyncpg.Pool):
    logger.info(f"my_chat_member event: status={event.new_chat_member.status}, chat={event.chat.id}")
    if event.new_chat_member.status != "administrator":
        return

    group_id = event.chat.id
    chat_info = await event.bot.get_chat(group_id)
    channel_id = chat_info.linked_chat_id
    if not channel_id:
        return

    channel_info = await event.bot.get_chat(channel_id)
    logger.info("checkpoint 1")

    logger.info("checkpoint 2")
    member = await event.bot.get_chat_member(channel_id, event.from_user.id)
    if member.status not in ("administrator", "creator"):
        return

    logger.info(f"PozdGPT has been added to {channel_info.title} channel")

    await db.execute(
        """
        INSERT INTO channels (channel_id, group_id, owner_user_id, active)
        VALUES ($1, $2, $3, TRUE)
        ON CONFLICT (channel_id) DO UPDATE
        SET group_id = EXCLUDED.group_id, owner_user_id = EXCLUDED.owner_user_id, active = TRUE
        """,
        channel_id, group_id, event.from_user.id,
    )

    await event.bot.send_message(
        event.from_user.id,
        f"Канал {channel_info.title} привязан!"
    )