"""Обработчик обычных текстовых сообщений."""
import logging
from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from app.llm import LLMError
from app.services.assistant import AssistantError, AssistantService
from app.telegram_text import split_formatted_text

logger = logging.getLogger(__name__)
router = Router(name="messages")
router.message.filter(F.chat.type == "private")


@router.message(F.text, ~F.text.startswith("/"))
async def answer(
    message: Message,
    assistant: AssistantService,
) -> None:
    if message.from_user is None:
        return

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
            response = await assistant.answer(
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                text=text.strip(),
            )

    except (LLMError, AssistantError) as exc:
        await message.answer(
            str(exc),
            parse_mode=None,
        )
        return
    except Exception:
        logger.exception("Необработанная ошибка при обработке сообщения")
        await message.answer(
            "Не удалось обработать сообщение",
            parse_mode=None,
        )
        return

    for part in split_formatted_text(response):
        await message.answer(
            part,
            parse_mode="HTML",
        )