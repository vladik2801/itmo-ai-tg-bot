from decimal import Decimal

import asyncpg
from app.constants import DEFAULT_MODE, TEMPERATURE_OPTIONS
from app.history import trim_history
from app.modes import MODES


class DialogRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ensure_user_settings(
        self,
        user_id: int,
        *,
        mode: str = DEFAULT_MODE,
        temperature: float = 0.3,
    ) -> None:
        if mode not in MODES:
            raise ValueError("Неизвестный режим")

        if temperature not in TEMPERATURE_OPTIONS:
            raise ValueError("Допустимые температуры: 0.0, 0.3, 0.7, 1.0")

        await self._pool.execute(
            """
            INSERT INTO user_settings (user_id, mode, temperature)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            mode,
            Decimal(str(temperature)),
        )

    async def set_temperature(
            self,
            user_id: int,
            temperature: float,
    ) -> None:
        if temperature not in TEMPERATURE_OPTIONS:
            raise ValueError("Недопустимая температура")

        await self._pool.execute(
            """
            INSERT INTO user_settings (user_id, temperature)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET temperature = EXCLUDED.temperature
            """,
            user_id,
            Decimal(str(temperature)),
        )
    async def get_history(
            self,
            chat_id: int,
            limit: int = 20,
            max_chars: int = 12000,
    ) -> list[dict[str, str]]:
        if limit <= 0 or max_chars <= 0:
            raise ValueError("Лимиты истории должны быть положительными")

        rows = await self._pool.fetch(
            """
            SELECT role, content
            FROM messages
            WHERE chat_id = $1
            ORDER BY id DESC
            LIMIT $2
            """,
            chat_id,
            limit,
        )
        return trim_history(rows, max_chars)

    async def save_exchange(
        self,
        chat_id: int,
        question: str,
        answer: str,
    ) -> None:
        if not question.strip() or not answer.strip():
            raise ValueError("Вопрос и ответ не должны быть пустыми")

        query = """
            INSERT INTO messages (chat_id, role, content)
            VALUES ($1, $2, $3)
        """

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(query, chat_id, "user", question)
                await connection.execute(query, chat_id, "assistant", answer)

    async def clear_history(self, chat_id: int) -> int:
        result = await self._pool.execute(
            "DELETE FROM messages WHERE chat_id = $1",
            chat_id,
        )
        return int(result.split()[-1])

    async def get_user_settings(self, user_id: int) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            """
            SELECT mode, temperature
            FROM user_settings
            WHERE user_id = $1
            """,
            user_id,
        )

    async def set_mode(
            self,
            user_id: int,
            chat_id: int,
            mode: str,
            temperature: float,
    ) -> None:
        if mode not in MODES:
            raise ValueError("Неизвестный режим")

        if temperature not in TEMPERATURE_OPTIONS:
            raise ValueError("Недопустимая температура")

        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO user_settings (user_id, temperature)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    user_id,
                    Decimal(str(temperature)),
                )

                current_mode = await connection.fetchval(
                    """
                    SELECT mode
                    FROM user_settings
                    WHERE user_id = $1
                    FOR UPDATE
                    """,
                    user_id,
                )

                if current_mode == mode:
                    return

                await connection.execute(
                    """
                    UPDATE user_settings
                    SET mode = $2
                    WHERE user_id = $1
                    """,
                    user_id,
                    mode,
                )

                await connection.execute(
                    "DELETE FROM messages WHERE chat_id = $1",
                    chat_id,
                )