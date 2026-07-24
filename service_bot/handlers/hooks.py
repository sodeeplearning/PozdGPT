import asyncpg
from loguru import logger

from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated


router = Router()


@router.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated, db: asyncpg.Pool):
    if event.new_chat_member.status != ChatMemberStatus.ADMINISTRATOR:
        return

    group_id = event.chat.id
    chat_info = await event.bot.get_chat(group_id)
    channel_id = chat_info.linked_chat_id
    if not channel_id:
        await event.bot.send_message(
            event.from_user.id,
            f"Группа {chat_info.title} не связана ни с одним каналом",
        )
        return

    logger.info(f"PozdGPT has been added to {chat_info.title} group")

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
        f"Группа-дискуссия {chat_info.title} привязана!"
    )
