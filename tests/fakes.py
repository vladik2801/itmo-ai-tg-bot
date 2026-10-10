"""Управляемые заглушки внешних зависимостей: LLM, хранилище, Telegram."""

from dataclasses import dataclass
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, User

from app.constants import DEFAULT_MODE, TEMPERATURE_OPTIONS
from app.history import trim_history
from app.modes import MODES
from tests.helpers import TOKEN


@dataclass
class LLMCall:
    messages: list[dict[str, str]]
    temperature: float


class FakeLLM:
    def __init__(self, *replies: str | Exception) -> None:
        self._replies = list(replies) or ["ответ модели"]
        self.calls: list[LLMCall] = []

    async def generate(self, messages: list[dict[str, str]], temperature: float) -> str:
        self.calls.append(LLMCall([dict(m) for m in messages], temperature))
        reply = self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeRepository:
    def __init__(self) -> None:
        self.settings: dict[int, dict] = {}
        self.messages: list[tuple[int, str, str]] = []

    async def ensure_user_settings(
        self, user_id: int, *, mode: str = DEFAULT_MODE, temperature: float = 0.3
    ) -> None:
        self.settings.setdefault(user_id, {"mode": mode, "temperature": temperature})

    async def get_user_settings(self, user_id: int):
        return self.settings.get(user_id)

    async def set_temperature(self, user_id: int, temperature: float) -> None:
        if temperature not in TEMPERATURE_OPTIONS:
            raise ValueError("Недопустимая температура")
        row = self.settings.setdefault(user_id, {"mode": DEFAULT_MODE, "temperature": 0.3})
        row["temperature"] = temperature

    async def set_mode(self, user_id: int, chat_id: int, mode: str, temperature: float) -> None:
        if mode not in MODES:
            raise ValueError("Неизвестный режим")
        row = self.settings.setdefault(user_id, {"mode": DEFAULT_MODE, "temperature": temperature})
        if row["mode"] == mode:
            return
        row["mode"] = mode
        await self.clear_history(chat_id)

    async def get_history(self, chat_id: int, limit: int = 20, max_chars: int = 12000):
        rows = [m for m in self.messages if m[0] == chat_id][::-1][:limit]
        return trim_history(({"role": r, "content": c} for _, r, c in rows), max_chars)

    async def save_exchange(self, chat_id: int, question: str, answer: str) -> None:
        if not question.strip() or not answer.strip():
            raise ValueError("Вопрос и ответ не должны быть пустыми")
        self.messages.append((chat_id, "user", question))
        self.messages.append((chat_id, "assistant", answer))

    async def clear_history(self, chat_id: int) -> int:
        before = len(self.messages)
        self.messages = [m for m in self.messages if m[0] != chat_id]
        return before - len(self.messages)

    def history_of(self, chat_id: int) -> list[tuple[str, str]]:
        return [(role, content) for cid, role, content in self.messages if cid == chat_id]


class FakeSession:
    def __init__(self) -> None:
        self.methods: list[TelegramMethod] = []

    async def __call__(self, bot: Bot, method: TelegramMethod, *args, **kwargs):
        self.methods.append(method)
        return True

    async def close(self) -> None:
        return None

    def sent_messages(self) -> list[SendMessage]:
        return [m for m in self.methods if isinstance(m, SendMessage)]


def make_bot() -> Bot:
    bot = Bot(TOKEN)
    bot.session = FakeSession()
    return bot


def make_message(
    bot: Bot,
    text: str | None,
    *,
    user_id: int = 42,
    chat_type: str = "private",
    chat_id: int | None = None,
) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=user_id if chat_id is None else chat_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="Студент"),
        text=text,
    ).as_(bot)


def make_callback(bot: Bot, data: str | None, *, user_id: int = 42) -> CallbackQuery:
    return CallbackQuery(
        id="1",
        from_user=User(id=user_id, is_bot=False, first_name="Студент"),
        chat_instance="test",
        message=make_message(bot, "меню", user_id=user_id),
        data=data,
    ).as_(bot)
