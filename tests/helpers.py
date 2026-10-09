"""Общие константы и фабрики для тестов."""

from app.config import Settings

TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk"


LLM_ENV = {
    "LLM_API_KEY": "test-llm-key",
    "LLM_BASE_URL": "https://llm.example.test/v1",
    "LLM_MODEL": "test-model",
}
REQUIRED_ENV = {
    "BOT_TOKEN": TOKEN,
    "POSTGRES_PASSWORD": "test-password",
    **LLM_ENV,
}


def make_settings(**overrides) -> Settings:
    values = {
        "bot_token": TOKEN,
        "postgres_password": "unused",
        "llm_api_key": LLM_ENV["LLM_API_KEY"],
        "llm_base_url": LLM_ENV["LLM_BASE_URL"],
        "llm_model": LLM_ENV["LLM_MODEL"],
    }
    values.update(overrides)
    return Settings(**values)
