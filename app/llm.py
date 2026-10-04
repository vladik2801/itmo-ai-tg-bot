import logging
from time import monotonic
from uuid import uuid4
import aiohttp

from app.config import Settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Безопасная ошибка обращения к модели."""


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        self._model = settings.llm_model
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=aiohttp.ClientTimeout(total=settings.llm_timeout_seconds),
        )

    async def generate(self, messages: list[dict[str, str]],temperature: float,) -> str:
        request_id = uuid4().hex
        started = monotonic()
        status = "error"

        logger.info(
            "Начало LLM-запроса: id=%s model=%s",
            request_id,
            self._model,
        )

        try:
            async with self._session.post(
                    self._url,
                    json={
                        "model": self._model,
                        "temperature": temperature,
                        "messages": messages
                    },
                    allow_redirects=False,
                    raise_for_status=False,  # Проверяем HTTP-статус самостоятельно.
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "Ошибка HTTP: id=%s status=%s",
                        request_id,
                        response.status,
                    )

                    if response.status == 429:
                        raise LLMError(
                            "Превышен лимит запросов. Попробуйте позже."
                        )

                    raise LLMError(
                        "Не удалось получить ответ модели. Попробуйте позже."
                    )

                try:
                    data = await response.json()
                except (ValueError, aiohttp.ContentTypeError):
                    logger.warning("Некорректный JSON: id=%s", request_id)
                    raise LLMError(
                        "Сервис модели вернул некорректные данные."
                    ) from None

                # Проверяем структуру ответа перед обращением к полям.
                if not isinstance(data, dict):
                    raise LLMError("Некорректный формат ответа модели.")

                choices = data.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise LLMError("Модель не вернула вариантов ответа.")

                choice = choices[0]
                if not isinstance(choice, dict):
                    raise LLMError("Некорректный формат варианта ответа.")

                message = choice.get("message")
                if not isinstance(message, dict):
                    raise LLMError("В ответе модели отсутствует сообщение.")

                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise LLMError("Модель не вернула текстовый ответ.")

                # При достижении лимита текст может быть неполным.
                if choice.get("finish_reason") == "length":
                    logger.warning(
                        "Ответ обрезан лимитом токенов: id=%s",
                        request_id,
                    )

                status = "ok"
                return content.strip()

        except TimeoutError:
            status = "timeout"
            raise LLMError(
                "Модель не успела ответить. Попробуйте ещё раз."
            ) from None

        except aiohttp.ClientError:
            status = "network_error"
            logger.warning("Ошибка соединения с LLM: id=%s", request_id)
            raise LLMError(
                "Ошибка связи с сервисом модели. Попробуйте позже."
            ) from None

        finally:
            logger.info(
                "Завершение LLM-запроса: id=%s status=%s duration=%.2fs",
                request_id,
                status,
                monotonic() - started,
            )
    async def close(self) -> None:
        await self._session.close()