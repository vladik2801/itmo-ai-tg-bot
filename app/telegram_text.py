"""Разбиение текста на сообщения Telegram."""

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