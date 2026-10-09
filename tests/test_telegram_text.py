"""Сценарий ТЗ 8: длинный ответ разбивается без потери текста."""

import re
from html import unescape

import pytest

from app.telegram_text import TELEGRAM_MESSAGE_LIMIT, split_formatted_text


def plain(parts: list[str]) -> str:
    joined = "".join(parts)
    return unescape(re.sub(r"</?(pre|code)>", "", joined))


def test_short_text_is_one_part():
    # Act
    parts = split_formatted_text("Привет!")
    # Assert
    assert parts == ["Привет!"]


def test_long_text_is_split_without_loss_and_in_order():
    # Arrange
    text = "".join(f"Абзац {i}. " + "слово " * 120 + "\n\n" for i in range(60))
    # Act
    parts = split_formatted_text(text)
    # Assert
    assert len(parts) > 1
    assert all(len(part) <= TELEGRAM_MESSAGE_LIMIT for part in parts)
    assert plain(parts) == text


def test_text_without_any_separator_is_split_without_loss():
    # Arrange
    text = "я" * 10_000
    # Act
    parts = split_formatted_text(text)
    # Assert
    assert all(len(part) <= TELEGRAM_MESSAGE_LIMIT for part in parts)
    assert "".join(parts) == text




def test_long_code_block_is_split_into_valid_code_parts():
    # Arrange
    code = "".join(f"x{i} = a < b && c > {i}\n" for i in range(1_500))
    text = f"```python\n{code}```"
    # Act
    parts = split_formatted_text(text)
    # Assert
    assert len(parts) > 1
    assert all(len(part) <= TELEGRAM_MESSAGE_LIMIT for part in parts)
    assert all(part.startswith("<pre><code>") and part.endswith("</code></pre>") for part in parts)
    assert plain(parts) == code


def test_whitespace_only_text_gives_no_parts():
    assert split_formatted_text(" \n\t ") == []


@pytest.mark.parametrize("size", [4095, 4096, 4097, 8192])
def test_boundary_lengths(size):
    # Arrange
    text = "ж" * size
    # Act
    parts = split_formatted_text(text)
    # Assert
    assert all(len(part) <= TELEGRAM_MESSAGE_LIMIT for part in parts)
    assert "".join(parts) == text
