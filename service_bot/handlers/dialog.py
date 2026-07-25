import asyncpg
import re
import uuid

from aiogram import Router, F
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import StateFilter
from aiogram.types import Message, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from chat import chatbot
from memory import memory
from config import Payment


router = Router()

mention_re = re.compile(r"^@pozdgpt_bot\b[,:]?\s*", re.IGNORECASE)


class GeneratingState(StatesGroup):
    generating = State()


@router.message(F.text, F.chat.type == ChatType.PRIVATE, StateFilter(None))
async def chat_response(message: Message, state: FSMContext):
    await state.set_state(GeneratingState.generating)
    try:
        temp_message = await message.reply(f"PozdGPT думает...")
        messages = memory.read_history(message.from_user.id)
        messages.append({"role": "user", "content": message.text})

        ai_response = await chatbot.non_stream(messages)

        await temp_message.delete()
        memory.add_qa(message.from_user.id, message.text, ai_response)
        await message.reply(ai_response, parse_mode=ParseMode.MARKDOWN)
    finally:
        await state.clear()


@router.guest_message()
@router.message(F.chat.type.in_((ChatType.GROUP, ChatType.SUPERGROUP)), F.text.regexp(mention_re))
async def mention_response(message: Message, db: asyncpg.Pool):
    if not message.text:
        return
    question = mention_re.sub("", message.text).strip()
    if not question:
        return

    if message.reply_to_message and message.reply_to_message.text:
        question = f"{message.reply_to_message.text} \n{question}"

    ai_response = await chatbot.non_stream([{"role": "user", "content": question}])

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

    if message.from_user:
        await db.execute("""
            INSERT INTO users (tg_user_id, username, balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_user_id) DO NOTHING""",
            message.from_user.id, message.from_user.username, Payment.default_user_messages,
        )
