from collections.abc import Iterable, Mapping

def trim_history(
        newest_first : Iterable[Mapping[str,str]],
        max_chars: int,
) -> list[dict[str,str]]:
    if max_chars <= 0:
        raise ValueError("Лимит истории должен быть положительным")
    kept: list[dict[str,str]] = []
    total = 0
    for message in newest_first:
        size = len(message["content"])
        if total + size > max_chars:
            break
        kept.append({"role" : message["role"], "content" : message["content"]})
        total += size
    kept.reverse()
    while kept and kept[0]["role"] != "user":
        kept.pop(0)
    return kept