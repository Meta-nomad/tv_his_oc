import asyncio
import aiohttp
from services.cache import Cache
from services.exchange_api import ExchangeAPIService


async def main():
    cache = Cache()
    async with aiohttp.ClientSession() as session:
        ex = ExchangeAPIService(cache, session)
        for ex_name, base, quote in [
            ("binance", "ONDO", "USDT"),
            ("okx", "ONDO", "USDT"),
            ("kraken", "ONDO", "USD"),
            ("coinbase", "ONDO", "USD"),
            ("gateio", "ONDO", "USDT"),
            ("mexc", "ONDO", "USDT"),
            ("bybit", "ONDO", "USDT"),
            ("htx", "ONDO", "USDT"),
        ]:
            dt = await ex.get_earliest_date(ex_name, base, quote)
            print(f"{ex_name}:{base}{quote} -> {dt}")


asyncio.run(main())
