import aiohttp
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

BASE_URL = 'https://min-api.cryptocompare.com/data'
MAX_BACKTRACK_SECONDS = 365 * 15 * 86400

logger = logging.getLogger(__name__)


class CryptoCompareService:
    def __init__(self, cache, session: aiohttp.ClientSession, api_key: str = ''):
        self.cache = cache
        self._session = session
        self.api_key = api_key
        self._blocked = False

    def _headers(self) -> dict:
        if self.api_key:
            return {'authorization': f'Apikey {self.api_key}'}
        return {}

    async def _get(self, endpoint: str, params: dict | None = None, retries: int = 2):
        if self._blocked:
            return None
        url = f'{BASE_URL}/{endpoint}'
        headers = self._headers()
        for attempt in range(retries):
            try:
                async with self._session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 401:
                        self._blocked = True
                        return None
                    if resp.status != 200:
                        logger.debug('CryptoCompare %d for %s', resp.status, url)
                        return None
                    data = await resp.json()
                    if data.get('Response') == 'Error':
                        logger.debug('CryptoCompare error: %s', data.get('Message'))
                        return None
                    return data
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.debug('CryptoCompare request failed: %s', e)
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def get_earliest_date(self, fsym: str, tsym: str, exchange: str | None = None) -> datetime | None:
        cache_key = f'cc_earliest_{fsym}_{tsym}_{exchange or "agg"}'
        cached = self.cache.get(cache_key)
        if cached:
            return datetime.fromisoformat(cached)

        date = await self._try_all_data(fsym, tsym, exchange)
        if not date:
            date = await self._binary_search(fsym, tsym, exchange)
        if not date:
            date = await self._try_histohour(fsym, tsym, exchange)

        if date:
            self.cache.set(cache_key, date.isoformat(), ttl=86400)
        return date

    async def _try_all_data(self, fsym: str, tsym: str, exchange: str | None) -> datetime | None:
        params: dict[str, Any] = {
            'fsym': fsym.upper(),
            'tsym': tsym.upper(),
            'limit': 2000,
            'allData': 'true',
        }
        if exchange:
            params['e'] = exchange

        data = await self._get('v2/histoday', params)
        if not data:
            return None

        prices = data.get('Data', {}).get('Data', [])
        if not prices:
            return None

        for p in prices:
            if p.get('high', 0) or p.get('low', 0) or p.get('close', 0):
                return datetime.fromtimestamp(p['time'], tz=timezone.utc)
        return None

    async def _binary_search(self, fsym: str, tsym: str, exchange: str | None) -> datetime | None:
        now = int(time.time())
        current_ts = now
        earliest_ts = now
        found = False

        while current_ts > now - MAX_BACKTRACK_SECONDS:
            params: dict[str, Any] = {
                'fsym': fsym.upper(),
                'tsym': tsym.upper(),
                'limit': 2000,
                'toTs': current_ts,
            }
            if exchange:
                params['e'] = exchange

            data = await self._get('v2/histoday', params)
            if not data:
                break

            prices = data.get('Data', {}).get('Data', [])
            if not prices:
                break

            first_nonzero = None
            for p in prices:
                if p.get('high', 0) or p.get('low', 0) or p.get('close', 0):
                    first_nonzero = p
                    break

            if first_nonzero is None:
                if found:
                    break
                current_ts -= 2000 * 86400
                continue

            found = True
            earliest_ts = first_nonzero['time']

            if first_nonzero is prices[0] and len(prices) >= 2000:
                current_ts = earliest_ts
            else:
                break

        if found:
            return datetime.fromtimestamp(earliest_ts, tz=timezone.utc)
        return None

    async def _try_histohour(self, fsym: str, tsym: str, exchange: str | None) -> datetime | None:
        params: dict[str, Any] = {
            'fsym': fsym.upper(),
            'tsym': tsym.upper(),
            'limit': 2000,
            'toTs': int(time.time()),
        }
        if exchange:
            params['e'] = exchange

        data = await self._get('v2/histohour', params)
        if not data:
            return None

        prices = data.get('Data', {}).get('Data', [])
        if not prices:
            return None

        for p in prices:
            if p.get('high', 0) or p.get('low', 0) or p.get('close', 0):
                return datetime.fromtimestamp(p['time'], tz=timezone.utc)
        return None

    async def check_continuity(self, fsym: str, tsym: str, exchange: str | None = None, hours: int = 2000) -> tuple[int, float]:
        cache_key = f'cc_continuity_{fsym}_{tsym}_{exchange or "agg"}_{hours}'
        cached = self.cache.get(cache_key)
        if cached:
            return tuple(cached)

        params: dict[str, Any] = {
            'fsym': fsym.upper(),
            'tsym': tsym.upper(),
            'limit': min(hours, 2000),
        }
        if exchange:
            params['e'] = exchange

        data = await self._get('v2/histohour', params)
        if not data:
            return (999, 0.0)

        prices = data.get('Data', {}).get('Data', [])
        if not prices:
            return (999, 0.0)

        gaps = 0
        total_volume = 0.0
        nonzero_count = 0
        flat_candles = 0

        for i in range(1, len(prices)):
            curr = prices[i]
            prev = prices[i - 1]

            vol = float(curr.get('volumeto', 0) or 0)
            if vol > 0:
                total_volume += vol
                nonzero_count += 1

            time_diff = curr['time'] - prev['time']
            if time_diff > 7200:
                gaps += 1

            high = float(curr.get('high', 0) or 0)
            low = float(curr.get('low', 0) or 0)
            close = float(curr.get('close', 0) or 0)
            if high == low == close and close > 0:
                flat_candles += 1

        avg_volume = total_volume / max(nonzero_count, 1)
        score = gaps * 100 + flat_candles * 10

        self.cache.set(cache_key, (score, avg_volume), ttl=86400)
        return (score, avg_volume)
