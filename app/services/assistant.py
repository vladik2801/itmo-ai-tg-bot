"""Сервис обработки запросов пользователя."""

import asyncio
from collections import defaultdict

from app.config import Settings
from app.dialog_repository import DialogRepository
from app.llm import LLMClient
from app.prompts import DEFAULT_SYSTEM_PROMPT, STUDY_SYSTEM_PROMPT


SYSTEM_PROMPTS = {
    "default": DEFAULT_SYSTEM_PROMPT,
    "study": STUDY_SYSTEM_PROMPT,
}

class AssistantError(Exception):
    """Безопасная ошибка обработки запроса."""

class AssistantService:
    def __init__(
        self,
        llm: LLMClient,
        repository: DialogRepository,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._repository = repository
        self._settings = settings
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def answer(
        self,
        user_id: int,
        chat_id: int,
        text: str,
    ) -> str:
        text = text.strip()
        if not text:
            raise AssistantError("Запрос не должен быть пустым")

        async with self._locks[chat_id]:
            await self._repository.ensure_user_settings(
                user_id=user_id,
                temperature=self._settings.default_temperature,
            )

            user_settings = await self._repository.get_user_settings(user_id)
            if user_settings is None:
                raise AssistantError("Не удалось загрузить настройки пользователя")

            history = await self._repository.get_history(
                chat_id=chat_id,
                limit=self._settings.history_max_messages,
                max_chars=self._settings.history_max_chars,
            )

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPTS[user_settings["mode"]],
                },
                *history,
                {"role": "user", "content": text},
            ]

            response = await self._llm.generate(
                messages=messages,
                temperature=float(user_settings["temperature"]),
            )

            await self._repository.save_exchange(
                chat_id=chat_id,
                question=text,
                answer=response,
            )

            return response

    async def clear_history(self, chat_id: int) -> int:
        async with self._locks[chat_id]:
            return await self._repository.clear_history(chat_id)