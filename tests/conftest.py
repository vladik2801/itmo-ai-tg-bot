from collections.abc import AsyncIterator, Callable
from typing import Any
from unittest.mock import Mock

import pytest
import pytest_asyncio

from app.config import Settings
from app.llm import LLMClient
from app.services.assistant import AssistantService
from tests.fakes import FakeLLM, FakeRepository, FakeSession
from tests.helpers import REQUIRED_ENV, make_settings


@pytest.fixture
def required_env() -> dict[str, str]:
    return REQUIRED_ENV.copy()


@pytest.fixture
def settings_factory() -> Callable[..., Settings]:
    return make_settings


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def assistant(
    settings: Settings,
    fake_llm: FakeLLM,
    repository: FakeRepository,
) -> AssistantService:
    return AssistantService(
        llm=fake_llm,
        repository=repository,
        settings=settings,
    )


@pytest.fixture
def assistant_factory(
    settings: Settings,
    fake_llm: FakeLLM,
    repository: FakeRepository,
) -> Callable[..., AssistantService]:
    def factory(**overrides: Any) -> AssistantService:
        dependencies = {
            "llm": fake_llm,
            "repository": repository,
            "settings": settings,
        }
        dependencies.update(overrides)
        return AssistantService(**dependencies)

    return factory


@pytest.fixture
def http_session() -> FakeSession:
    return FakeSession()


@pytest_asyncio.fixture
async def llm_client(
    settings: Settings,
    http_session: FakeSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[LLMClient]:
    monkeypatch.setattr(
        "app.llm.aiohttp.ClientSession",
        Mock(return_value=http_session),
    )

    client = LLMClient(settings)
    try:
        yield client
    finally:
        await client.close()