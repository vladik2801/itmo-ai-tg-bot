import asyncio
import logging
from dataclasses import dataclass, field

import pytest
from aiohttp import web

from app.llm import LLMClient, LLMError
from tests.helpers import make_settings


@dataclass
class ServerState:
    requests: list[dict] = field(default_factory=list)
    headers: list[dict] = field(default_factory=list)
    status: int = 200
    body: object = None
    raw: str | None = None
    delay: float = 0.0


def ok_body(content="Ответ модели"):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


@pytest.fixture
async def llm_server(unused_tcp_port):
    state = ServerState(body=ok_body())

    async def handler(request: web.Request) -> web.Response:
        state.requests.append(await request.json())
        state.headers.append(dict(request.headers))
        if state.delay:
            await asyncio.sleep(state.delay)
        if state.raw is not None:
            return web.Response(text=state.raw, status=state.status, content_type="text/plain")
        return web.json_response(state.body, status=state.status)

    app = web.Application()
    app.router.add_post("/v1/chat/completions", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    state.url = f"http://127.0.0.1:{unused_tcp_port}/v1"
    yield state
    await runner.cleanup()


@pytest.fixture
async def make_client(llm_server):
    clients = []

    def factory(**overrides):
        client = LLMClient(make_settings(llm_base_url=llm_server.url, **overrides))
        clients.append(client)
        return client

    yield factory
    for client in clients:
        await client.close()


MESSAGES = [
    {"role": "system", "content": "Ты помощник."},
    {"role": "user", "content": "Первый вопрос"},
    {"role": "assistant", "content": "Первый ответ"},
    {"role": "user", "content": "Второй вопрос"},
]


async def test_request_carries_model_temperature_roles_and_order(llm_server, make_client):
    # Arrange
    client = make_client()
    # Act
    answer = await client.generate(MESSAGES, temperature=0.7)
    # Assert
    assert answer == "Ответ модели"
    (payload,) = llm_server.requests
    assert payload == {"model": "test-model", "temperature": 0.7, "messages": MESSAGES}
    assert llm_server.headers[0]["Authorization"] == "Bearer test-llm-key"


async def test_answer_is_stripped(llm_server, make_client):
    # Arrange
    llm_server.body = ok_body("  \n Ответ \n ")
    # Act
    answer = await make_client().generate(MESSAGES, temperature=0.0)
    # Assert
    assert answer == "Ответ"


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (429, "Превышен лимит запросов. Попробуйте позже."),
        (500, "Не удалось получить ответ модели. Попробуйте позже."),
        (401, "Не удалось получить ответ модели. Попробуйте позже."),
    ],
)
async def test_http_error_becomes_safe_message(llm_server, make_client, status, message):
    # Arrange
    llm_server.status = status
    llm_server.body = {"error": "secret details: key=test-llm-key"}
    # Act / Assert
    with pytest.raises(LLMError) as error:
        await make_client().generate(MESSAGES, temperature=0.3)
    assert str(error.value) == message


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"choices": []}, "Модель не вернула вариантов ответа."),
        ({}, "Модель не вернула вариантов ответа."),
        ({"choices": ["строка"]}, "Некорректный формат варианта ответа."),
        ({"choices": [{}]}, "В ответе модели отсутствует сообщение."),
        (ok_body(""), "Модель не вернула текстовый ответ."),
        (ok_body("   \n"), "Модель не вернула текстовый ответ."),
        ({"choices": [{"message": {"content": None}}]}, "Модель не вернула текстовый ответ."),
        ([1, 2, 3], "Некорректный формат ответа модели."),
    ],
)
async def test_malformed_or_empty_answer_is_rejected(llm_server, make_client, body, message):
    # Arrange
    llm_server.body = body
    # Act / Assert
    with pytest.raises(LLMError) as error:
        await make_client().generate(MESSAGES, temperature=0.3)
    assert str(error.value) == message


async def test_non_json_answer_is_rejected(llm_server, make_client):
    # Arrange
    llm_server.raw = "<html>Bad gateway</html>"
    # Act / Assert
    with pytest.raises(LLMError) as error:
        await make_client().generate(MESSAGES, temperature=0.3)
    assert str(error.value) == "Сервис модели вернул некорректные данные."


async def test_timeout_becomes_safe_message(llm_server, make_client):
    # Arrange
    llm_server.delay = 1.0
    client = make_client(llm_timeout_seconds=0.1)
    # Act / Assert
    with pytest.raises(LLMError) as error:
        await client.generate(MESSAGES, temperature=0.3)
    assert str(error.value) == "Модель не успела ответить. Попробуйте ещё раз."


async def test_connection_failure_becomes_safe_message_without_url(unused_tcp_port):
    # Arrange
    url = f"http://127.0.0.1:{unused_tcp_port}/v1"
    client = LLMClient(make_settings(llm_base_url=url))
    try:
        # Act / Assert
        with pytest.raises(LLMError) as error:
            await client.generate(MESSAGES, temperature=0.3)
        assert str(error.value) == "Ошибка связи с сервисом модели. Попробуйте позже."
        assert str(unused_tcp_port) not in str(error.value)
    finally:
        await client.close()


async def test_logs_contain_model_status_and_duration_but_no_secrets_or_dialog(
    llm_server, make_client, caplog
):
    # Arrange
    caplog.set_level(logging.INFO, logger="app.llm")
    # Act
    await make_client().generate(MESSAGES, temperature=0.3)
    # Assert
    log = "\n".join(record.getMessage() for record in caplog.records)
    assert "model=test-model" in log
    assert "status=ok" in log
    assert "duration=" in log
    for forbidden in ("test-llm-key", "Ты помощник", "Первый вопрос", "Ответ модели"):
        assert forbidden not in log
