from pathlib import Path

import pytest
from dotenv import dotenv_values

from app.config import ConfigError, Settings
from tests.helpers import LLM_ENV, TOKEN

BASE = {"BOT_TOKEN": TOKEN, "POSTGRES_PASSWORD": "db-secret", **LLM_ENV}
ROOT = Path(__file__).resolve().parents[1]


def load(tmp_path, **overrides):
    values = {**BASE, **overrides}
    return Settings.load(tmp_path / ".env", environ=values)


def test_llm_settings_are_read_from_environment(tmp_path):
    # Act
    config = load(tmp_path)
    # Assert
    assert config.llm_base_url == "https://llm.example.test/v1"
    assert config.llm_model == "test-model"
    assert "test-llm-key" not in repr(config)


def test_defaults_for_optional_limits(tmp_path):
    # Act
    config = load(tmp_path)
    # Assert
    assert (config.history_max_messages, config.context_max_chars) == (20, 12_000)
    assert config.default_temperature == 0.3
    assert config.llm_timeout_seconds == 30.0


@pytest.mark.parametrize("key", ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"])
def test_missing_required_llm_setting_gives_clear_safe_error(tmp_path, key):
    # Arrange
    values = {k: v for k, v in BASE.items() if k != key}
    # Act / Assert
    with pytest.raises(ConfigError) as error:
        Settings.load(tmp_path / ".env", environ=values)
    assert key in str(error.value)
    for secret in ("test-llm-key", "db-secret", TOKEN):
        assert secret not in str(error.value)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DEFAULT_TEMPERATURE", "0.5"),
        ("DEFAULT_TEMPERATURE", "abc"),
        ("HISTORY_MAX_MESSAGES", "0"),
        ("HISTORY_MAX_MESSAGES", "-3"),
        ("CONTEXT_MAX_CHARS", "abc"),
        ("LLM_TIMEOUT_SECONDS", "0"),
        ("LLM_TIMEOUT_SECONDS", "nan"),
    ],
)
def test_invalid_numeric_settings_are_rejected(tmp_path, key, value):
    # Act / Assert
    with pytest.raises(ConfigError, match=key):
        load(tmp_path, **{key: value})


def test_env_example_documents_llm_settings_without_real_secrets():
    # Arrange
    example = dotenv_values(ROOT / ".env.example")
    # Assert
    for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        assert key in example
    assert not example["LLM_API_KEY"]
    assert not example["BOT_TOKEN"]
