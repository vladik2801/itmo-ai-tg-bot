"""Сервис обработки запросов пользователя."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass

from app.config import Settings
from app.constants import TEMPERATURE_OPTIONS
from app.modes import MODES
from app.services.ports import DialogStore, LLMGateway


@dataclass(frozen=True)
class UserSettings:
    mode: str
    temperature: float
    model: str


class AssistantError(Exception):
    """Безопасная ошибка обработки запроса."""


class AssistantService:
    def __init__(
        self,
        llm: LLMGateway,
        repository: DialogStore,
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

            mode = MODES.get(user_settings.mode)
            if mode is None:
                raise AssistantError("Неизвестный режим ассистента")

            remaining_chars = self._settings.context_max_chars - len(mode.prompt) - len(text)

            if remaining_chars < 0:
                raise AssistantError("Запрос слишком длинный. Сократите сообщение.")

            history: list[dict[str, str]] = []
            if remaining_chars > 0 and mode.uses_history:
                history = await self._repository.get_history(
                    chat_id=chat_id,
                    limit=self._settings.history_max_messages,
                    max_chars=remaining_chars,
                )

            messages = [
                {"role": "system", "content": mode.prompt},
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
            model=self._settings.llm_model,
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
        if mode not in MODES:
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
