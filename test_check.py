import asyncio
import aiohttp
from services.cache import Cache
from services.coingecko import CoinGeckoService
from services.cryptocompare import CryptoCompareService
from services.exchange_api import ExchangeAPIService
from services.analyzer import Analyzer
from config.settings import CRYPTOCOMPARE_API_KEY


async def main():
    cache = Cache()
    async with aiohttp.ClientSession() as session:
        cg = CoinGeckoService(cache, session)
        cc = CryptoCompareService(cache, session, CRYPTOCOMPARE_API_KEY)
        ex = ExchangeAPIService(cache, session)
        analyzer = Analyzer(cg, cc, ex, cache)

        for ticker in ["ONDO", "BTC", "ETH", "ZEC"]:
            r = await analyzer.analyze(ticker)
            if r:
                print(f"{ticker}: {r.best_pair} ({r.best_exchange}, {r.best_date.strftime('%Y-%m-%d')})")
            else:
                print(f"{ticker}: not found")

asyncio.run(main())
