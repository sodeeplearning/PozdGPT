from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from worker import chatbot
from memory import memory


router = Router()


class GeneratingState(StatesGroup):
    generating = State()


@router.message(F.text, StateFilter(None))
async def stream_response(message: Message, state: FSMContext):
    await state.set_state(GeneratingState.generating)
    try:
        messages = memory.read_history(message.from_user.id)
        messages.append({"role": "user", "content": message.text})
        ai_response = await chatbot.non_stream(messages)
        memory.add_qa(message.from_user.id, message.text, ai_response)
        await message.reply(ai_response)
    finally:
        await state.clear()
