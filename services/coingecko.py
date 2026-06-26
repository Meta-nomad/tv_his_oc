import aiohttp
import asyncio
import logging
from typing import Any

BASE_URL = 'https://api.coingecko.com/api/v3'

logger = logging.getLogger(__name__)


class CoinGeckoService:
    def __init__(self, cache, session: aiohttp.ClientSession):
        self.cache = cache
        self._session = session

    async def _get(self, url: str, params: dict | None = None, retries: int = 3):
        for attempt in range(retries):
            try:
                async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        wait = min(60 * (attempt + 1), 180)
                        logger.warning('CoinGecko 429, waiting %ds', wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        logger.warning('CoinGecko %d for %s', resp.status, url)
                        return None
                    return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning('CoinGecko request failed (%s): %s', url, e)
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return None
        return None

    async def search_coins(self, query: str) -> list[dict]:
        cache_key = f'cg_search_{query.lower()}'
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        data = await self._get(f'{BASE_URL}/search', {'query': query})
        if data is None:
            return []
        coins = data.get('coins', [])
        self.cache.set(cache_key, coins, ttl=3600)
        return coins

    async def get_coin_info(self, coin_id: str) -> dict | None:
        cache_key = f'cg_coin_info_{coin_id}'
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        data = await self._get(f'{BASE_URL}/coins/{coin_id}')
        if data is None:
            return None
        self.cache.set(cache_key, data, ttl=3600)
        return data

    async def get_coin_tickers(self, coin_id: str) -> list[dict]:
        cache_key = f'cg_tickers_{coin_id}'
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        all_tickers: list[dict] = []
        page = 1
        while page <= 10:
            data = await self._get(
                f'{BASE_URL}/coins/{coin_id}/tickers',
                {'page': page, 'limit': 100},
            )
            if data is None:
                break
            tickers = data.get('tickers', [])
            if not tickers:
                break
            all_tickers.extend(tickers)
            page += 1

        self.cache.set(cache_key, all_tickers, ttl=3600)
        return all_tickers

    async def resolve_coin(self, symbol: str) -> dict | None:
        symbol = symbol.upper()

        search_results = await self.search_coins(symbol)
        exact = [c for c in search_results if c.get('symbol', '').upper() == symbol]
        exact.sort(key=lambda x: x.get('market_cap_rank', 9999) or 9999)

        if exact:
            coin_id = exact[0]['id']
            info = await self.get_coin_info(coin_id)
            if info:
                return info

        return None
