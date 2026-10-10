"""Проверки истории и настроек на настоящем PostgreSQL."""

import os

import pytest

from app.db import create_pool, initialize_bd
from app.dialog_repository import DialogRepository
from app.llm import LLMError
from app.services.assistant import AssistantService
from tests.fakes import FakeLLM
from tests.helpers import make_settings
from tests.test_integration import database as database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_INTEGRATION") != "1",
        reason="Для запуска установите RUN_INTEGRATION=1",
    ),
]


@pytest.fixture
async def pool(database):
    settings = database[0]
    pool = await create_pool(settings)

    try:
        await initialize_bd(pool)
        yield pool
    finally:
        await pool.close()


@pytest.fixture
def repository(pool):
    return DialogRepository(pool)


async def test_history_preserves_messages_and_roles(repository):
    await repository.save_exchange(1, "вопрос 1", "ответ 1")
    await repository.save_exchange(1, "вопрос 2", "ответ 2")

    history = await repository.get_history(1)

    assert history == [
        {"role": "user", "content": "вопрос 1"},
        {"role": "assistant", "content": "ответ 1"},
        {"role": "user", "content": "вопрос 2"},
        {"role": "assistant", "content": "ответ 2"},
    ]


async def test_users_have_separate_history(repository):
    await repository.save_exchange(1, "вопрос Ани", "ответ Ани")
    await repository.save_exchange(2, "вопрос Вани", "ответ Вани")

    first = await repository.get_history(1)
    second = await repository.get_history(2)

    assert [m["content"] for m in first] == ["вопрос Ани", "ответ Ани"]
    assert [m["content"] for m in second] == ["вопрос Вани", "ответ Вани"]


async def test_history_limits(repository):
    for i in range(1, 6):
        await repository.save_exchange(1, f"q{i}", f"a{i}")

    by_count = await repository.get_history(1, limit=4)
    by_size = await repository.get_history(1, max_chars=6)

    assert [m["content"] for m in by_count] == ["q4", "a4", "q5", "a5"]
    assert [m["content"] for m in by_size] == ["q5", "a5"]


async def test_mode_change_clears_only_own_history(repository):
    await repository.ensure_user_settings(1)
    await repository.set_temperature(1, 0.7)
    await repository.save_exchange(1, "q1", "a1")
    await repository.save_exchange(2, "q2", "a2")

    await repository.set_mode(
        user_id=1,
        chat_id=1,
        mode="translate",
        temperature=0.3,
    )

    settings = await repository.get_user_settings(1)

    assert settings["mode"] == "translate"
    assert float(settings["temperature"]) == 0.7
    assert await repository.get_history(1) == []
    assert len(await repository.get_history(2)) == 2


async def test_reset_keeps_settings_and_other_history(repository):
    await repository.ensure_user_settings(1, mode="translate", temperature=0.7)
    await repository.save_exchange(1, "Привет", "Hello")
    await repository.save_exchange(2, "вопрос", "ответ")

    removed = await repository.clear_history(1)

    settings = await repository.get_user_settings(1)

    assert removed == 2
    assert await repository.get_history(1) == []
    assert len(await repository.get_history(2)) == 2
    assert settings["mode"] == "translate"
    assert float(settings["temperature"]) == 0.7


async def test_temperature_changes_only_for_one_user(repository):
    await repository.ensure_user_settings(1)
    await repository.ensure_user_settings(2)

    await repository.set_temperature(1, 1.0)

    first = await repository.get_user_settings(1)
    second = await repository.get_user_settings(2)

    assert float(first["temperature"]) == 1.0
    assert float(second["temperature"]) == 0.3


async def test_new_service_reads_saved_context(repository, database):
    await repository.ensure_user_settings(1, mode="translate", temperature=0.7)
    await repository.save_exchange(1, "Привет", "Hello")

    # Новое соединение и новый сервис используют уже записанные данные.
    new_pool = await create_pool(database[0])

    try:
        new_repository = DialogRepository(new_pool)
        llm = FakeLLM("Good morning")
        service = AssistantService(llm, new_repository, make_settings())

        settings = await service.get_settings(1)
        await service.answer(
            user_id=1,
            chat_id=1,
            text="Доброе утро",
        )

        assert settings.mode == "translate"
        assert settings.temperature == 0.7
        assert llm.calls[0].temperature == 0.7
        assert llm.calls[0].messages[1:] == [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Доброе утро"},
        ]
    finally:
        await new_pool.close()


async def test_llm_error_does_not_save_failed_exchange(repository):
    llm = FakeLLM("ответ 1", LLMError("сбой"), "ответ 3")
    service = AssistantService(llm, repository, make_settings())

    await service.answer(user_id=1, chat_id=1, text="вопрос 1")

    with pytest.raises(LLMError):
        await service.answer(user_id=1, chat_id=1, text="вопрос 2")

    await service.answer(user_id=1, chat_id=1, text="вопрос 3")

    history = await repository.get_history(1)

    assert [m["content"] for m in history] == [
        "вопрос 1",
        "ответ 1",
        "вопрос 3",
        "ответ 3",
    ]
    assert [m["content"] for m in llm.calls[2].messages[1:]] == [
        "вопрос 1",
        "ответ 1",
        "вопрос 3",
    ]
