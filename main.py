import asyncio
import logging
import sys

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

from config.settings import BOT_TOKEN, CRYPTOCOMPARE_API_KEY
from bot.handlers import router, setup_analyzer
from services.cache import Cache
from services.coingecko import CoinGeckoService
from services.cryptocompare import CryptoCompareService
from services.exchange_api import ExchangeAPIService
from services.analyzer import Analyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env file")

    cache = Cache()
    logger.info("Cache initialized at %s", cache._get_path('test').parent)

    async with aiohttp.ClientSession() as session:
        coingecko = CoinGeckoService(cache, session)
        cryptocompare = CryptoCompareService(cache, session, CRYPTOCOMPARE_API_KEY)
        exchange_api = ExchangeAPIService(cache, session)
        analyzer = Analyzer(coingecko, cryptocompare, exchange_api, cache)

        setup_analyzer(analyzer)
        logger.info("Analyzer initialized")

        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher()
        dp.include_router(router)

        logger.info("Starting bot polling...")
        await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
