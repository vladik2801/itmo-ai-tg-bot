"""Сервис обработки запросов пользователя."""

import asyncio
from collections import defaultdict

from app.config import Settings
from app.dialog_repository import DialogRepository
from app.llm import LLMClient
from app.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    STUDY_SYSTEM_PROMPT,
    TRANSLATE_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
)
from dataclasses import dataclass


TEMPERATURE_OPTIONS = (0.0, 0.3, 0.7, 1.0)

SYSTEM_PROMPTS = {
    "default": DEFAULT_SYSTEM_PROMPT,
    "study": STUDY_SYSTEM_PROMPT,
    "translate": TRANSLATE_SYSTEM_PROMPT,
    "summary" : SUMMARY_SYSTEM_PROMPT
}

@dataclass(frozen=True)
class UserSettings:
    mode: str
    temperature: float

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
            user_settings = await self.get_settings(user_id)

            system_prompt = SYSTEM_PROMPTS.get(user_settings.mode)
            if system_prompt is None:
                raise AssistantError("Неизвестный режим ассистента")

            remaining_chars = (
                self._settings.context_max_chars
                - len(system_prompt)
                - len(text)
            )

            if remaining_chars < 0:
                raise AssistantError(
                    "Запрос слишком длинный. Сократите сообщение."
                )

            history = []
            if remaining_chars > 0 and user_settings.mode != "summary":
                history = await self._repository.get_history(
                    chat_id=chat_id,
                    limit=self._settings.history_max_messages,
                    max_chars=remaining_chars,
                )

            messages = [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": text},
            ]

            response = await self._llm.generate(
                messages=messages,
                temperature=user_settings.temperature,
            )

            await self._repository.save_exchange(
                chat_id=chat_id,
                question=text,
                answer=response,
            )

            return response

    async def get_settings(self, user_id: int) -> UserSettings:
        await self._repository.ensure_user_settings(
            user_id=user_id,
            temperature=self._settings.default_temperature,
        )

        row = await self._repository.get_user_settings(user_id)
        if row is None:
            raise AssistantError("Не удалось загрузить настройки")

        return UserSettings(
            mode=row["mode"],
            temperature=float(row["temperature"]),
        )

    async def set_temperature(
            self,
            user_id: int,
            chat_id: int,
            temperature: float,
    ) -> None:
        if temperature not in TEMPERATURE_OPTIONS:
            raise AssistantError("Недопустимая температура")

        async with self._locks[chat_id]:
            await self._repository.set_temperature(
                user_id=user_id,
                temperature=temperature,
            )

    async def set_mode(
        self,
        user_id: int,
        chat_id: int,
        mode: str,
    ) -> None:
        if mode not in SYSTEM_PROMPTS:
            raise AssistantError("Неизвестный режим ассистента")

        async with self._locks[chat_id]:
            await self._repository.set_mode(
                user_id=user_id,
                chat_id=chat_id,
                mode=mode,
                temperature=self._settings.default_temperature,
            )

    async def clear_history(self, chat_id: int) -> int:
        async with self._locks[chat_id]:
            return await self._repository.clear_history(chat_id)