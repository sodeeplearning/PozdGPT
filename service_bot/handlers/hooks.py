import asyncpg
from aiogram import Router
from aiogram.types import ChatMemberUpdated


router = Router()


@router.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated, db: asyncpg.Pool):
    group_id = event.chat.id
    chat_info = await event.bot.get_chat(group_id)
    channel_id = chat_info.linked_chat_id
    if not channel_id:
        return

    member = await event.bot.get_chat_member(channel_id, event.from_user.id)
    if member.status not in ("administrator", "creator"):
        return

    await db.execute(
        "INSERT OR IGNORE INTO users VALUES ($1, 0)",
        event.from_user.id,
    )
    await db.execute(
        "INSERT OR REPLACE INTO channels VALUES ($1, $2, $3, 1)",
        (channel_id, group_id, event.from_user.id),
    )
    await event.bot.send_message(
        event.from_user.id,
        f"Канал {chat_info.title} привязан!"
    )
