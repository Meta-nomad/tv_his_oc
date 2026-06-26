"""
Telegram bot handlers using aiogram 3.x.
"""

import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from services.analyzer import analyze_ticker, ExchangeResult

logger = logging.getLogger(__name__)

router = Router()

START_TEXT = (
    "👋 <b>TradingView History Bot</b>\n\n"
    "Отправьте тикер монеты — я найду биржу с <b>самой длинной</b> доступной историей цены.\n\n"
    "При одинаковой глубине истории выбирается биржа с <b>наиболее непрерывным</b> часовым графиком.\n\n"
    "Примеры:\n"
    "<code>BTC</code>\n"
    "<code>ETH</code>\n"
    "<code>ZEC</code>\n"
    "<code>DOGE</code>\n"
    "<code>SOL</code>"
)


def _gap_label(r: ExchangeResult) -> str:
    """Human-readable continuity label based on gap_ratio."""
    if not r.gap_ratio_checked:
        return ""
    ratio = r.gap_ratio
    if ratio < 0.01:
        return "🟢 Без разрывов"
    elif ratio < 0.05:
        return "🟡 Редкие разрывы"
    elif ratio < 0.20:
        return "🟠 Заметные разрывы"
    else:
        return "🔴 Много разрывов"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(START_TEXT, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(START_TEXT, parse_mode="HTML")


@router.message(F.text)
async def handle_ticker(message: Message) -> None:
    raw = message.text.strip()

    if not raw or len(raw) > 20 or " " in raw or raw.startswith("/"):
        await message.answer(
            "Введите тикер монеты, например: <code>BTC</code>", parse_mode="HTML"
        )
        return

    ticker = raw.upper()
    wait_msg = await message.answer(
        f"🔍 Ищу историю для <b>{ticker}</b>...", parse_mode="HTML"
    )

    try:
        result = await analyze_ticker(ticker)
    except Exception as e:
        logger.exception("Error analyzing ticker %s: %s", ticker, e)
        await wait_msg.edit_text(
            "⚠️ Произошла ошибка при запросе данных. Попробуйте позже."
        )
        return

    if result is None:
        await wait_msg.edit_text(
            f"❌ Монета <b>{ticker}</b> не найдена. Проверьте тикер.",
            parse_mode="HTML",
        )
        return

    best = result.best
    date_str  = best.earliest_date.strftime("%Y-%m-%d")
    gap_label = _gap_label(best)

    text = (
        f"📊 <b>Монета:</b> {result.ticker}\n\n"
        f"✅ <b>Рекомендуемый символ TradingView:</b>\n"
        f"<code>{best.tv_symbol}</code>\n\n"
        f"🏦 <b>Биржа:</b> {best.exchange_tv}\n\n"
        f"📅 <b>История с:</b> {date_str}\n"
    )

    if gap_label:
        text += f"📈 <b>Часовой график:</b> {gap_label}\n"

    text += f"\n🔗 <b>Ссылка:</b>\n{best.tv_url}\n"

    if result.alternatives:
        text += "\n📋 <b>Альтернативы:</b>\n"
        for alt in result.alternatives:
            alt_gap = f"  {_gap_label(alt)}" if alt.gap_ratio_checked else ""
            text += f"• <code>{alt.tv_symbol}</code>{alt_gap}\n"

    await wait_msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)
