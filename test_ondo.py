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

        r = await analyzer.analyze("ONDO")
        if r:
            with open("test_ondo_result.txt", "w", encoding="utf-8") as f:
                f.write(f"best_pair={r.best_pair}\n")
                f.write(f"best_exchange={r.best_exchange}\n")
                f.write(f"best_date={r.best_date}\n")
                f.write(f"quote={r.quote}\n")
                f.write(f"alternatives={r.alternatives}\n")
            print("Done, wrote test_ondo_result.txt")
        else:
            print("Not found")

asyncio.run(main())
