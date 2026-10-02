from aiogram import Router

from app.handlers.commands import router as commands_router
from app.handlers.messages import router as messages_router
router = Router(name="main")

router.include_router(commands_router)
router.include_router(messages_router)