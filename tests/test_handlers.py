"""Обработчики Telegram: маршрутизация, точные тексты и безопасные ответы."""

import pytest
from aiogram.dispatcher.event.bases import UNHANDLED

from app.handlers import commands, messages
from app.llm import LLMError
from app.services.assistant import AssistantService
from tests.fakes import (
    FakeLLM,
    FakeRepository,
    make_bot,
    make_message,
)
from tests.helpers import make_settings


@pytest.fixture
def bot():
    return make_bot()


def make_assistant(*replies):
    llm = FakeLLM(*replies)
    store = FakeRepository()
    return AssistantService(llm, store, make_settings()), llm, store


def texts(bot):
    return [m.text for m in bot.session.sent_messages()]


async def route(router, message, bot, assistant):
    return await router.propagate_event("message", message, bot=bot, assistant=assistant)


@pytest.mark.parametrize("router", [commands.router, messages.router])
async def test_group_chat_messages_are_ignored(bot, router):
    # Arrange
    assistant, llm, _ = make_assistant()
    message = make_message(
        bot, "/study" if router is commands.router else "вопрос", chat_type="group"
    )
    # Act
    result = await route(router, message, bot, assistant)
    # Assert
    assert result is UNHANDLED
    assert bot.session.methods == []
    assert llm.calls == []


async def test_message_without_text_is_ignored(bot):
    # Arrange
    assistant, llm, _ = make_assistant()
    # Act
    result = await route(messages.router, make_message(bot, None), bot, assistant)
    # Assert
    assert result is UNHANDLED
    assert llm.calls == []


async def test_reset_clears_history_keeps_settings_and_confirms(bot):
    # Arrange
    assistant, _, store = make_assistant()
    await assistant.set_temperature(user_id=42, chat_id=42, temperature=0.0)
    await assistant.answer(user_id=42, chat_id=42, text="вопрос")
    # Act
    await route(commands.router, make_message(bot, "/reset"), bot, assistant)
    # Assert
    assert store.history_of(42) == []
    assert (await assistant.get_settings(42)).temperature == 0.0
    assert texts(bot) == ["История диалога очищена. Настройки сохранены."]


async def test_plain_message_gets_model_answer(bot):
    # Arrange
    assistant, llm, _ = make_assistant("Цикл повторяет действия.")
    # Act
    await route(messages.router, make_message(bot, "Что такое цикл?"), bot, assistant)
    # Assert
    assert texts(bot) == ["Цикл повторяет действия."]
    assert llm.calls[0].messages[-1] == {"role": "user", "content": "Что такое цикл?"}


@pytest.mark.parametrize(
    "error_text",
    [
        "Модель не успела ответить. Попробуйте ещё раз.",
        "Не удалось получить ответ модели. Попробуйте позже.",
        "Модель не вернула текстовый ответ.",
    ],
)
async def test_llm_error_becomes_exact_safe_message(bot, error_text):
    # Arrange
    assistant, _, store = make_assistant(LLMError(error_text))
    # Act
    await route(messages.router, make_message(bot, "вопрос"), bot, assistant)
    # Assert
    assert texts(bot) == [error_text]
    assert store.history_of(42) == []
