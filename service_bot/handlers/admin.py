import asyncio
import asyncpg
from loguru import logger

from aiogram import Router, Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import TelegramBotParams


router = Router()


async def send_everyone_task(bot: Bot, db: asyncpg.Pool, text: str, report_chat_id: int):
    rows = await db.fetch("SELECT tg_user_id FROM users")
    user_ids = [row["tg_user_id"] for row in rows]

    success = 0
    failed = 0
    for tg_user_id in user_ids:
        try:
            await bot.send_message(tg_user_id, text)
            success += 1
        except TelegramForbiddenError:
            failed += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(tg_user_id, text)
                success += 1
            except Exception as e2:
                failed += 1
                logger.error(f"Failed retry to {tg_user_id}: {e2}")
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {tg_user_id}: {e}")
        await asyncio.sleep(0.05)

    await bot.send_message(
        report_chat_id,
        f"Рассылка завершена. Успешно: {success}. Неуспешно: {failed}"
    )


@router.message(Command("send_everyone"))
async def send_message_everyone(message: Message, command: CommandObject, db: asyncpg.Pool):
    if message.from_user.id not in TelegramBotParams.admins_ids:
        return
    if not command.args:
        await message.reply("Использование: /send_everyone текст сообщения")
        return

    asyncio.create_task(send_everyone_task(message.bot, db, command.args, message.chat.id))
    await message.reply("Рассылка запущена в фоне.")
