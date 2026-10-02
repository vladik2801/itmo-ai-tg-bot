"""Обработчик обычных текстовых сообщений."""

from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from app.llm import LLMError
from app.services.assistant import AssistantService, AssistantError
from app.telegram_text import split_text
router = Router(name="messages")
router.message.filter(F.chat.type == "private")


@router.message(F.text, ~F.text.startswith("/"))
async def answer(
    message: Message,
    assistant: AssistantService,
) -> None:
    text = message.text

    if text is None or not text.strip():
        await message.answer(
            "Введите непустой запрос.",
            parse_mode=None,
        )
        return

    try:
        async with ChatActionSender.typing(
            bot=message.bot,
            chat_id=message.chat.id,
        ):
            response = await assistant.answer(text.strip())

    except LLMError as exc:
        await message.answer(
            str(exc),
            parse_mode=None,
        )
        return

    for part in split_text(response):
        await message.answer(
            part,
            parse_mode=None,
        )