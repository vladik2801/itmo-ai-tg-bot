"""Разбиение текста на сообщения Telegram."""
import re
from html import escape
TELEGRAM_MESSAGE_LIMIT = 4096



def split_formatted_text(text: str) -> list[str]:
    limit = 2000
    parts: list[str] = []

    def append_parts(fragment: str, is_code: bool) -> None:
        for offset in range(0, len(fragment), limit):
            chunk = fragment[offset : offset + limit]

            if not chunk.strip():
                continue
            escaped = escape(chunk, quote=False)

            if is_code:
                parts.append(f"<pre><code>{escaped}</code></pre>")
            else:
                parts.append(escaped)

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