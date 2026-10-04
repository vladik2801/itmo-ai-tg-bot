"""Разбиение текста на сообщения Telegram."""
import re
from html import escape
TELEGRAM_MESSAGE_LIMIT = 4096


def split_text(
    text: str,
    limit: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    if not 1 <= limit <= TELEGRAM_MESSAGE_LIMIT:
        raise ValueError(
            f"limit должен быть от 1 до {TELEGRAM_MESSAGE_LIMIT}"
        )

    if not text.strip():
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts: list[str] = []

    while len(text) > limit:
        paragraph_end = text.rfind("\n\n", 0, limit)

        if paragraph_end > 0:
            split_at = paragraph_end + 2
        else:
            split_at = limit

        part = text[:split_at]
        if part.strip():
            parts.append(part)
        text = text[split_at:]

    if text.strip():
        parts.append(text)

    return parts

def split_formatted_text(text: str) -> list[str]:
    """Подготовить части ответа с HTML-блоками кода."""

    # Запас по длине, в том числе для символов вроде emoji.
    limit = 2000
    parts: list[str] = []

    def append_parts(fragment: str, is_code: bool) -> None:
        for offset in range(0, len(fragment), limit):
            chunk = fragment[offset : offset + limit]

            if not chunk.strip():
                continue

            # Защищаем <, > и &, особенно важные в коде C++.
            escaped = escape(chunk, quote=False)

            if is_code:
                parts.append(f"<pre><code>{escaped}</code></pre>")
            else:
                parts.append(escaped)

    # Поддерживает блоки вида ```python\nкод\n```
    # и блоки без указания языка.
    pattern = re.compile(
        r"```[^\r\n`]*\r?\n(.*?)```",
        re.DOTALL,
    )

    position = 0

    for match in pattern.finditer(text):
        append_parts(text[position : match.start()], is_code=False)
        append_parts(match.group(1), is_code=True)
        position = match.end()

    append_parts(text[position:], is_code=False)

    return parts