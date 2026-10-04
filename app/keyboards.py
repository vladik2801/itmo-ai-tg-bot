from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.constants import TEMPERATURE_OPTIONS

class TemperatureKeyboard:
    PREF = "temperature"
    @classmethod
    def encode(cls, temperature: float) -> str:
        return f"{cls.PREF}{temperature: .1f}"

    @classmethod
    def parse(cls, data: str | None) -> float | None:
        if data is None:
            return None
        for temperature in TEMPERATURE_OPTIONS:
            if data == cls.encode(temperature):
                return temperature
        return None
    @classmethod
    def build(cls, current: float | None = None) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text = f"✓ {value:.1f}" if value == current else f"{value:.1f}",
                        callback_data = cls.encode(value)
                    )
                    for value in TEMPERATURE_OPTIONS
                ]
            ]
        )