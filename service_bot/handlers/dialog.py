import asyncio
import asyncpg
from loguru import logger
import re
import uuid

from aiogram import Router, F
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from chat import chatbot
from commenter import commenter
from memory import memory
from utils.dbfuncs import add_user


router = Router()

mention_re = re.compile(r"^@pozdgpt_bot\b[,:]?\s*", re.IGNORECASE)


class GeneratingState(StatesGroup):
    generating = State()


@router.message(Command("clear"), F.chat.type == ChatType.PRIVATE)
async def clear_chat_history(message: Message):
    memory.clear_history(message.from_user.id)
    await message.reply("PozdGPT забыл о чем с вами говорил!")


@router.message(F.text, F.chat.type == ChatType.PRIVATE, StateFilter(None))
async def chat_response(message: Message, state: FSMContext):
    await state.set_state(GeneratingState.generating)
    try:

        temp_message = await message.reply(f"PozdGPT думает...")
        messages = memory.read_history(message.from_user.id)
        messages.append({"role": "user", "content": message.text})

        try:
            ai_response = await chatbot.non_stream(messages)
        except Exception as e:
            ai_response = "PozdGPT наебнулся, попробуйте ещё раз"
            logger.error(f"Error occurred while LLM requesting: {e}")

        await temp_message.delete()
        memory.add_qa(message.from_user.id, message.text, ai_response)
        await message.reply(ai_response, parse_mode=ParseMode.MARKDOWN)
    finally:
        await state.clear()


@router.guest_message()
@router.message(F.chat.type.in_((ChatType.GROUP, ChatType.SUPERGROUP)), F.text.regexp(mention_re))
async def mention_response(message: Message, db: asyncpg.Pool):
    if not message.text or not message.from_user:
        return

    row = await db.fetchrow(
        """
        UPDATE users
        SET balance = balance - 1
        WHERE tg_user_id = $1 AND balance > 0
        RETURNING balance
        """,
        message.from_user.id,
    )
    if row is None:
        await message.reply("Недостаточно баланса")
        return

    question = mention_re.sub("", message.text).strip()
    if not question:
        return

    messages = []
    if message.reply_to_message and message.reply_to_message.text:
        if message.reply_to_message.from_user.id == message.bot.id:
            messages.append({"role": "assistant", "content": message.reply_to_message.text})
        else:
            question = f"{message.reply_to_message.text} \n{question}"
    messages.append({"role": "user", "content": question})

    try:
        ai_response = await chatbot.non_stream(messages)
    except Exception as e:
        ai_response = "PozdGPT наебнулся, попробуйте ещё раз"
        logger.error(f"Error occurred while LLM requesting: {e}")

    if message.guest_query_id:
        await message.bot.answer_guest_query(
            guest_query_id=message.guest_query_id,
            result=InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="Guest Mode ответ",
                input_message_content=InputTextMessageContent(
                    message_text=ai_response,
                    parse_mode=ParseMode.MARKDOWN,
                ),
            ),
        )
    else:
        await message.reply(ai_response, parse_mode=ParseMode.MARKDOWN)

    await add_user(message.from_user.id, message.from_user.username, db)


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
        await message.reply(generated_comment, parse_mode=ParseMode.MARKDOWN)
    except TelegramRetryAfter as e:
        logger.warning(
            f"Failed to write comment due to flood control. Sleeping {e.retry_after} seconds")
        await asyncio.sleep(e.retry_after)
        await message.reply(generated_comment, parse_mode=ParseMode.MARKDOWN)
