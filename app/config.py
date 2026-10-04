"""Чтение и сборка настроек приложения."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from app import config_validation as validation
from app.config_validation import ConfigError as ConfigError


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(repr=False)
    postgres_password: str = field(repr=False)
    llm_api_key: str = field(repr=False)
    llm_base_url: str
    llm_model: str

    telegram_proxy_url: str = field(default="", repr=False)
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "bot"
    postgres_user: str = "bot"
    log_level: str = "INFO"
    health_port: int = 8080

    llm_timeout_seconds: float = 30.0
    default_temperature: float = 0.3
    history_max_messages: int = 20
    context_max_chars: int = 12_000

    @classmethod
    def load(
        cls,
        env_file: Path | str = ".env",
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "Settings":
        values = {
            **dotenv_values(env_file, interpolate=False),
            **(os.environ if environ is None else environ),
        }

        def value(key: str, default: str = "") -> str:
            result = values.get(key)
            return default if result is None else result

        return cls(
            bot_token=validation.bot_token(value("BOT_TOKEN")),
            postgres_password=validation.required(
                "POSTGRES_PASSWORD", value("POSTGRES_PASSWORD")
            ),
            telegram_proxy_url=validation.telegram_proxy_url(
                value("TELEGRAM_PROXY_URL")
            ),
            postgres_host=value("POSTGRES_HOST", "127.0.0.1"),
            postgres_port=validation.port(
                "POSTGRES_PORT", value("POSTGRES_PORT", "5432")
            ),
            postgres_db=value("POSTGRES_DB", "bot"),
            postgres_user=value("POSTGRES_USER", "bot"),
            log_level=validation.log_level(value("LOG_LEVEL", "INFO")),
            health_port=validation.port(
                "HEALTH_PORT", value("HEALTH_PORT", "8080")
            ),
            llm_api_key=validation.required(
                "LLM_API_KEY", value("LLM_API_KEY")
            ),
            llm_base_url=validation.required(
                "LLM_BASE_URL", value("LLM_BASE_URL")
            ),
            llm_model=validation.required(
                "LLM_MODEL", value("LLM_MODEL")
            ),
            llm_timeout_seconds=validation.positive_float(
                "LLM_TIMEOUT_SECONDS", value("LLM_TIMEOUT_SECONDS", "30")
            ),
            default_temperature=validation.temperature(
                "DEFAULT_TEMPERATURE", value("DEFAULT_TEMPERATURE", "0.3")
            ),
            history_max_messages=validation.positive_int(
                "HISTORY_MAX_MESSAGES", value("HISTORY_MAX_MESSAGES", "20")
            ),
            context_max_chars=validation.positive_int(
                "CONTEXT_MAX_CHARS",
                value(
                    "CONTEXT_MAX_CHARS",
                    value("HISTORY_MAX_CHARS", "12000"),
                ),
            ),
        )