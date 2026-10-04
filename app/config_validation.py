import math
from urllib.parse import urlsplit

from aiogram.utils.token import TokenValidationError, validate_token
from app.constants import TEMPERATURE_OPTIONS


class ConfigError(ValueError):
    """Ошибка настройки без секретных значений в сообщении."""


def required(key: str, value : str) -> str:
    result = value.strip()
    if not result:
        raise ConfigError(f"{key}: не задана обязательная настройка")
    return result


def positive_int(key: str, value: str) -> int:
    message = f"{key}: требуется положительное целое число."
    try:
        result = int(value)
    except:
        raise ConfigError(message) from None
    if result <= 0:
        raise ConfigError(message)
    return result


def positive_float(key: str, value: str) -> float:
    message = f"{key}: требуется положительное целое число."
    try:
        result = float(value)
    except ValueError:
        raise ConfigError(message) from None
    if not math.isfinite(result) or result <= 0:
        raise ConfigError(message)
    return result


def temperature(key: str, value: str) -> float:
    message = f"{key}: допустимы только 0.0, 0.3, 0.7 или 1.0."
    try:
        result = float(value)
    except ValueError:
        raise ConfigError(message) from None
    if result not in TEMPERATURE_OPTIONS:
        raise ConfigError(message)
    return result


def port(key: str, value : str) -> int:
    min_port_num = 1
    max_port_num = 65535
    try:
        message = f"{key}: нужен номер порта от 1 до 65535."
        result = int(value)
        if not min_port_num <= result <= max_port_num:
            raise ValueError
        return result
    except ValueError:
        raise ConfigError(message) from None

def bot_token(value: str) -> str:
    message =  "BOT_TOKEN: укажите токен, полученный у BotFather."
    try:
        validate_token(value)
    except TokenValidationError:
        raise ConfigError(message) from None
    return value

def log_level(value: str) -> str:
    result = value.upper()
    range_valid_log = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    message = "LOG_LEVEL: используйте DEBUG, INFO, WARNING, ERROR или CRITICAL."
    if result not in range_valid_log:
        raise ConfigError(message)

    return result

def telegram_proxy_url(value: str) -> str:
    message = "TELEGRAM_PROXY_URL: нужен http://host:port или socks5://host:port. При необходимости добавьте user:password@."
    if not value:
        return value

    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "socks5"}
            or not parsed.hostname
            or not parsed.port
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
    except ValueError:
        raise ConfigError(
            message
        ) from None

    return value