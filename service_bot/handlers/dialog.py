import re

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from chat import chatbot
from memory import memory


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
        await message.reply(ai_response)
    finally:
        await state.clear()


@router.message(F.chat.type.in_((ChatType.GROUP, ChatType.SUPERGROUP)), F.text.regexp(mention_re))
async def mention_response(message: Message):
    question = mention_re.sub("", message.text, count=1).strip()
    if not question:
        return

    if message.reply_to_message and message.reply_to_message.text:
        question = f"{message.reply_to_message.text} Вопрос: {question}"

    messages = [{"role": "user", "content": question}]
    ai_response = await chatbot.non_stream(messages)
    await message.reply(ai_response)
