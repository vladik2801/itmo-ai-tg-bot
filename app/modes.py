"""Перечень режимов ассистента: ключ, команда, инструкция и тексты в одном месте."""

from dataclasses import dataclass

from app.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    STUDY_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    TRANSLATE_SYSTEM_PROMPT,
)

@dataclass(frozen=True)
class AssistantMode:
    key: str
    command : str | None
    prompt : str
    description: str
    switched_message: str
    uses_history: bool = True


MODES: dict[str, AssistantMode] = {
    mode.key: mode
    for mode in (
        AssistantMode(
            key = "default",
            command= None,
            prompt= DEFAULT_SYSTEM_PROMPT,
            description="",
            switched_message="",
        ),
        AssistantMode(
            key = "study",
            command="study",
            prompt= STUDY_SYSTEM_PROMPT,
            description="помощь с программированием",
            switched_message="Включен режим программирования! Введи свой запрос.",
        ),
        AssistantMode(
            key="translate",
            command="translate",
            prompt=TRANSLATE_SYSTEM_PROMPT,
            description="перевод текстов",
            switched_message=(
                "Включён режим перевода.\n\n"
                "По умолчанию rus -> eng\n"
                "Для другого языка укажи его в запросе\n\n"
                "Отправь текст для перевода."
            ),
        ),
        AssistantMode(
            key="summary",
            command="summary",
            prompt= SUMMARY_SYSTEM_PROMPT,
            description="конспект текста",
            switched_message= "Включён режим конспекта. Пришли текст — я выделю основную мысль и ключевые тезисы.",
            uses_history= False,
            ),
        )
}
COMMAND_MODES: dict[str, AssistantMode] = {
    mode.command: mode for mode in MODES.values() if mode.command is not None
}