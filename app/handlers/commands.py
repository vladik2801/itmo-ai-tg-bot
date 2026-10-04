from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.config_validation import temperature
from app.keyboards import TemperatureKeyboard
from app.modes import COMMAND_MODES, MODES
from app.services.assistant import AssistantError, AssistantService


router = Router(name="commands")
router.message.filter(F.chat.type == "private")

@router.message(Command("start"))
async def start(message : Message) -> None:
    await message.answer(
        "Привет! Я AI-ассистент.\n\n"
        "/study — помощь с программированием\n"
        "/translate — перевод текстов\n"
        "/settings — настройки температуры\n"
        "/summary - конспект текста\n"
        "/reset — очистить историю диалога\n\n"
        "Выбери режим и отправь сообщение.",
        parse_mode= None,
    )

@router.message(Command(*COMMAND_MODES))
async def switch_mode(
    message: Message,
    command: CommandObject,
    assistant: AssistantService,
) -> None:
    if message.from_user is None:
        return

    mode = COMMAND_MODES[command.command]
    try:
        await assistant.set_mode(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            mode= mode.key,
        )
    except AssistantError as exc:
        await message.answer(str(exc), parse_mode=None)
        return

    await message.answer(
        mode.switched_message,
        parse_mode=None,
    )
@router.message(Command("reset"))
async def reset(
    message: Message,
    assistant: AssistantService,
) -> None:
    await assistant.clear_history(message.chat.id)

    await message.answer(
        "История диалога очищена. Настройки сохранены.",
        parse_mode=None,
    )

@router.message(Command("settings"))
async def settings_command(
    message: Message,
    assistant: AssistantService,
) -> None:
    if message.from_user is None:
        return

    try:
        settings = await assistant.get_settings(message.from_user.id)
    except AssistantError as exc:
        await message.answer(str(exc), parse_mode=None)
        return
    mode = MODES[settings.mode]
    mode_name = f"/{mode.command}" if mode.command else mode.key

    await message.answer(
        f"Режим: {mode_name}\n"
        f"Модель: {settings.model}\n"
        f"Температура: {settings.temperature:.1f}\n\n"
        "Выберите новое значение температуры:",
        reply_markup=TemperatureKeyboard.build(current=settings.temperature),
        parse_mode=None,
    )


@router.callback_query(F.data.startswith(TemperatureKeyboard.PREF))
async def temperature_callback(
    callback: CallbackQuery,
    assistant: AssistantService,
) -> None:
    message = callback.message

    if (
        not isinstance(message, Message)
        or message.chat.type != "private"
        or message.chat.id != callback.from_user.id
    ):
        await callback.answer("Настройки доступны в личном чате.")
        return

    temperature = TemperatureKeyboard.parse(callback.data)
    if temperature is None:
        await callback.answer("Недопустимое значение.", show_alert=True)
        return

    await callback.answer()

    try:
        await assistant.set_temperature(
            user_id=callback.from_user.id,
            chat_id=message.chat.id,
            temperature=temperature,
        )
    except AssistantError as exc:
        await message.answer(str(exc), parse_mode=None)
        return

    await message.edit_text(
        f"Температура изменена на {temperature:.1f}.",
        reply_markup=None,
        parse_mode=None,
    )