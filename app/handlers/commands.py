from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="commands")
router.message.filter(F.chat.type == "private")

@router.message(Command("start"))
async def start(message : Message) -> None:
    await message.answer(
        "Привет! Чтобы отправить вопрос по программированию /study",
        parse_mode= None,
    )

@router.message(Command("study"))
async def study(message : Message) -> None:
    await message.answer(
        "Включен режим программирования! Введи свой запрос",
        parse_mode= None,
    )