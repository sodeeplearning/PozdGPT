from aiogram import Router, F
from aiogram.types import Message
import asyncpg


router = Router()


@router.message(F.is_automatic_forward == True)
async def write_comment(message: Message, db: asyncpg.Pool):
    pass
