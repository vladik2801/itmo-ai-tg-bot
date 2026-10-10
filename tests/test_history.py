import pytest

from app.history import trim_history


def messages_newest_first(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"role": role, "content": content} for role, content in pairs]


def test_history_is_returned_in_chronological_order():
    # Arrange
    newest_first = messages_newest_first(
        ("assistant", "a2"), ("user", "q2"), ("assistant", "a1"), ("user", "q1")
    )
    # Act
    result = trim_history(newest_first, max_chars=100)
    # Assert
    assert [m["content"] for m in result] == ["q1", "a1", "q2", "a2"]
    assert [m["role"] for m in result] == ["user", "assistant", "user", "assistant"]


def test_oldest_messages_are_dropped_first_when_limit_is_exceeded():
    # Arrange
    newest_first = messages_newest_first(
        ("assistant", "bbbb"), ("user", "bbbb"), ("assistant", "aaaa"), ("user", "aaaa")
    )
    # Act
    result = trim_history(newest_first, max_chars=8)
    # Assert
    assert [m["content"] for m in result] == ["bbbb", "bbbb"]


def test_history_never_starts_with_orphan_assistant_reply():
    # Arrange
    newest_first = messages_newest_first(("assistant", "ответ"), ("user", "очень длинный вопрос"))
    # Act
    result = trim_history(newest_first, max_chars=5)
    # Assert
    assert result == []


def test_empty_history_gives_empty_result():
    assert trim_history([], max_chars=10) == []


@pytest.mark.parametrize("limit", [0, -1])
def test_non_positive_limit_is_rejected(limit):
    with pytest.raises(ValueError):
        trim_history([], max_chars=limit)


def test_history_has_no_gap_when_a_middle_message_does_not_fit():
    # Arrange
    newest_first = messages_newest_first(
        ("assistant", "a3"),
        ("user", "очень-очень длинный вопрос"),
        ("assistant", "a1"),
        ("user", "q1"),
    )
    # Act
    result = trim_history(newest_first, max_chars=10)
    # Assert
    assert result == []
