import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.enums.chat_action import ChatAction

from services.analyzer import Analyzer

logger = logging.getLogger(__name__)

router = Router()
_analyzer: Analyzer | None = None


def setup_analyzer(analyzer: Analyzer):
    global _analyzer
    _analyzer = analyzer


@router.message(Command('start'))
async def cmd_start(message: types.Message):
    text = (
        "Отправьте тикер монеты:\n\n"
        "Примеры:\n"
        "BTC\n"
        "ETH\n"
        "ZEC\n"
        "DOGE\n"
        "SOL\n\n"
        "Я найду биржу с самой длинной историей цены для TradingView."
    )
    await message.answer(text)


@router.message()
async def handle_ticker(message: types.Message):
    ticker = message.text.strip().upper()
    if not ticker or not ticker.isalnum():
        await message.answer("Пожалуйста, отправьте корректный тикер (только буквы и цифры).")
        return

    if _analyzer is None:
        await message.answer("Сервис временно недоступен. Попробуйте позже.")
        return

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        result = await _analyzer.analyze(ticker)
    except Exception:
        logger.exception("Analysis error for %s", ticker)
        await message.answer("Недостаточно данных для определения самой длинной истории.")
        return

    if result is None:
        await message.answer("Монета не найдена. Проверьте тикер.")
        return

    await message.answer(result.to_message())
