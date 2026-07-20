from aiogram import Router

from .send import send_router


router = Router()

router.include_routers(
    send_router,
)
