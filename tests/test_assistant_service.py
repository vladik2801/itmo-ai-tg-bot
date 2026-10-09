"""Обязательные сценарии ТЗ 1–7 на уровне сервиса (без Telegram, LLM и PostgreSQL)."""

import pytest

from app.llm import LLMError
from app.prompts import STUDY_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT, TRANSLATE_SYSTEM_PROMPT
from app.services.assistant import AssistantError, AssistantService
from tests.fakes import FakeLLM, FakeRepository
from tests.helpers import make_settings


def build(*replies, **settings):
    llm = FakeLLM(*replies)
    store = FakeRepository()
    service = AssistantService(llm, store, make_settings(**settings))
    return service, llm, store


async def test_message_goes_to_llm_with_study_prompt_by_default():
    # Arrange
    service, llm, _ = build("Ответ")
    # Act
    answer = await service.answer(user_id=1, chat_id=1, text="  Что такое цикл?  ")
    # Assert
    assert answer == "Ответ"
    assert llm.calls[0].messages == [
        {"role": "system", "content": STUDY_SYSTEM_PROMPT},
        {"role": "user", "content": "Что такое цикл?"},
    ]
    assert llm.calls[0].temperature == 0.3


@pytest.mark.parametrize(
    ("mode", "prompt"),
    [("translate", TRANSLATE_SYSTEM_PROMPT), ("summary", SUMMARY_SYSTEM_PROMPT)],
)
async def test_active_mode_prompt_is_used(mode, prompt):
    # Arrange
    service, llm, _ = build()
    await service.set_mode(user_id=1, chat_id=1, mode=mode)
    # Act
    await service.answer(user_id=1, chat_id=1, text="текст")
    # Assert
    assert llm.calls[0].messages[0] == {"role": "system", "content": prompt}


async def test_empty_message_is_rejected_before_llm_call():
    # Arrange
    service, llm, _ = build()
    # Act / Assert
    with pytest.raises(AssistantError, match="Запрос не должен быть пустым"):
        await service.answer(user_id=1, chat_id=1, text="   ")
    assert llm.calls == []


async def test_summary_mode_does_not_send_previous_messages():
    # Arrange
    service, llm, _ = build()
    await service.set_mode(user_id=1, chat_id=1, mode="summary")
    await service.answer(user_id=1, chat_id=1, text="первый текст")
    # Act
    await service.answer(user_id=1, chat_id=1, text="второй текст")
    # Assert
    assert [m["role"] for m in llm.calls[1].messages] == ["system", "user"]


async def test_histories_of_two_users_do_not_mix():
    # Arrange
    service, llm, _ = build("ответ Ани", "ответ Вани", "ещё Ане")
    await service.answer(user_id=1, chat_id=1, text="вопрос Ани")
    await service.answer(user_id=2, chat_id=2, text="вопрос Вани")
    # Act
    await service.answer(user_id=1, chat_id=1, text="второй вопрос Ани")
    # Assert
    sent = [m["content"] for m in llm.calls[2].messages[1:]]
    assert sent == ["вопрос Ани", "ответ Ани", "второй вопрос Ани"]
    assert all("Вани" not in content for content in sent)


async def test_history_is_sent_in_chronological_order_with_roles():
    # Arrange
    service, llm, _ = build("a1", "a2", "a3")
    await service.answer(user_id=1, chat_id=1, text="q1")
    await service.answer(user_id=1, chat_id=1, text="q2")
    # Act
    await service.answer(user_id=1, chat_id=1, text="q3")
    # Assert
    history = llm.calls[2].messages
    assert [(m["role"], m["content"]) for m in history] == [
        ("system", STUDY_SYSTEM_PROMPT),
        ("user", "q1"),
        ("assistant", "a1"),
        ("user", "q2"),
        ("assistant", "a2"),
        ("user", "q3"),
    ]


async def test_message_count_limit_keeps_latest_messages_in_order():
    # Arrange
    service, llm, _ = build(*[f"a{i}" for i in range(1, 6)], history_max_messages=4)
    for i in range(1, 5):
        await service.answer(user_id=1, chat_id=1, text=f"q{i}")
    # Act
    await service.answer(user_id=1, chat_id=1, text="q5")
    # Assert
    sent = llm.calls[4].messages
    assert sent[0]["role"] == "system"
    assert [m["content"] for m in sent[1:]] == ["q3", "a3", "q4", "a4", "q5"]


async def test_size_limit_drops_old_history_but_keeps_prompt_and_current_request():
    # Arrange
    text = "текущий запрос"
    budget = len(STUDY_SYSTEM_PROMPT) + len(text) + 30
    service, llm, _ = build("о" * 20, "о" * 20, context_max_chars=budget)
    await service.answer(user_id=1, chat_id=1, text="старый запрос 1")
    await service.answer(user_id=1, chat_id=1, text="старый запрос 2")
    # Act
    await service.answer(user_id=1, chat_id=1, text=text)
    # Assert
    sent = llm.calls[2].messages
    assert sent[0] == {"role": "system", "content": STUDY_SYSTEM_PROMPT}
    assert sent[-1] == {"role": "user", "content": text}
    assert sum(len(m["content"]) for m in sent) <= budget
    assert sent[1]["role"] == "user" or len(sent) == 2


async def test_too_long_request_is_rejected_with_exact_message():
    # Arrange
    service, llm, _ = build(context_max_chars=len(STUDY_SYSTEM_PROMPT) + 5)
    # Act / Assert
    with pytest.raises(AssistantError) as error:
        await service.answer(user_id=1, chat_id=1, text="очень длинный запрос")
    assert str(error.value) == "Запрос слишком длинный. Сократите сообщение."
    assert llm.calls == []


async def test_mode_switch_clears_history_and_persists_new_mode():
    # Arrange
    service, llm, store = build()
    await service.answer(user_id=1, chat_id=1, text="вопрос по коду")
    assert store.history_of(1)
    # Act
    await service.set_mode(user_id=1, chat_id=1, mode="translate")
    # Assert
    assert store.history_of(1) == []
    assert (await service.get_settings(1)).mode == "translate"
    await service.answer(user_id=1, chat_id=1, text="Привет")
    assert llm.calls[-1].messages == [
        {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
        {"role": "user", "content": "Привет"},
    ]


async def test_mode_switch_does_not_touch_other_users():
    # Arrange
    service, _, store = build()
    await service.answer(user_id=1, chat_id=1, text="вопрос Ани")
    await service.answer(user_id=2, chat_id=2, text="вопрос Вани")
    # Act
    await service.set_mode(user_id=1, chat_id=1, mode="translate")
    # Assert
    assert store.history_of(1) == []
    assert len(store.history_of(2)) == 2
    assert (await service.get_settings(2)).mode == "study"


async def test_unknown_mode_is_rejected():
    # Arrange
    service, _, store = build()
    # Act / Assert
    with pytest.raises(AssistantError, match="Неизвестный режим"):
        await service.set_mode(user_id=1, chat_id=1, mode="hacker")
    assert store.settings == {}


async def test_first_contact_uses_study_mode_and_reports_model():
    # Arrange
    service, _, _ = build()
    # Act
    settings = await service.get_settings(user_id=7)
    # Assert
    assert (settings.mode, settings.temperature, settings.model) == ("study", 0.3, "test-model")


async def test_reset_clears_only_callers_history_and_keeps_settings():
    # Arrange
    service, _, store = build()
    await service.set_mode(user_id=1, chat_id=1, mode="translate")
    await service.set_temperature(user_id=1, chat_id=1, temperature=0.7)
    await service.answer(user_id=1, chat_id=1, text="Привет")
    await service.answer(user_id=2, chat_id=2, text="Вопрос")
    # Act
    removed = await service.clear_history(chat_id=1)
    # Assert
    assert removed == 2
    assert store.history_of(1) == []
    assert len(store.history_of(2)) == 2
    settings = await service.get_settings(1)
    assert (settings.mode, settings.temperature) == ("translate", 0.7)


@pytest.mark.parametrize("value", [0.0, 0.3, 0.7, 1.0])
async def test_allowed_temperature_is_saved_and_used_from_next_request(value):
    # Arrange
    service, llm, _ = build()
    # Act
    await service.set_temperature(user_id=1, chat_id=1, temperature=value)
    await service.answer(user_id=1, chat_id=1, text="вопрос")
    # Assert
    assert (await service.get_settings(1)).temperature == value
    assert llm.calls[0].temperature == value


@pytest.mark.parametrize("value", [0.5, -1.0, 2.0, 0.31])
async def test_invalid_temperature_is_rejected_before_storage(value):
    # Arrange
    service, _, store = build()
    # Act / Assert
    with pytest.raises(AssistantError) as error:
        await service.set_temperature(user_id=1, chat_id=1, temperature=value)
    assert str(error.value) == "Недопустимая температура"
    assert store.settings == {}


async def test_temperature_of_one_user_does_not_change_another():
    # Arrange
    service, llm, _ = build()
    await service.set_temperature(user_id=1, chat_id=1, temperature=1.0)
    # Act
    await service.answer(user_id=2, chat_id=2, text="вопрос")
    # Assert
    assert llm.calls[0].temperature == 0.3


async def test_llm_error_propagates_and_nothing_is_saved():
    # Arrange
    service, llm, store = build(LLMError("Модель не успела ответить. Попробуйте ещё раз."))
    # Act / Assert
    with pytest.raises(LLMError, match="Модель не успела ответить"):
        await service.answer(user_id=1, chat_id=1, text="вопрос")
    assert store.history_of(1) == []
    assert len(llm.calls) == 1


async def test_chat_works_again_after_llm_error():
    # Arrange
    service, _, store = build(LLMError("сбой"), "Теперь работает")
    with pytest.raises(LLMError):
        await service.answer(user_id=1, chat_id=1, text="первый")
    # Act
    answer = await service.answer(user_id=1, chat_id=1, text="второй")
    # Assert
    assert answer == "Теперь работает"
    assert store.history_of(1) == [("user", "второй"), ("assistant", "Теперь работает")]
