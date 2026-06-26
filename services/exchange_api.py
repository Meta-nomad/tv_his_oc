import aiohttp
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

logger = logging.getLogger(__name__)


class ExchangeAPIService:
    def __init__(self, cache, session: aiohttp.ClientSession):
        self.cache = cache
        self._session = session
        self.handlers: dict[str, Callable] = {
            'binance': self._binance,
            'kraken': self._kraken,
            'bitstamp': self._bitstamp,
            'coinbase': self._coinbase,
            'bitfinex': self._bitfinex,
            'poloniex': self._poloniex,
            'bittrex': self._bittrex,
            'bybit': self._bybit,
            'okx': self._okx,
            'gateio': self._gateio,
            'htx': self._htx,
            'mexc': self._mexc,
        }

    async def _get(self, url: str, params: dict | None = None, retries: int = 2):
        for _ in range(retries):
            try:
                async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(3)
                        continue
                    if resp.status != 200:
                        return None
                    return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                continue
        return None

    async def get_earliest_date(self, exchange: str, base: str, quote: str) -> datetime | None:
        key = exchange.lower().strip().replace(' ', '').replace('-', '')
        handler = self.handlers.get(key)
        if not handler:
            return None
        cache_key = f'ex_{key}_{base}_{quote}'
        cached = self.cache.get(cache_key)
        if cached:
            return datetime.fromisoformat(cached)
        try:
            dt = await handler(base.upper(), quote.upper())
            if dt:
                self.cache.set(cache_key, dt.isoformat(), ttl=86400)
            return dt
        except Exception as e:
            logger.debug('Exchange API error %s: %s', key, e)
            return None

    async def _binance(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}{quote}'
        data = await self._get(
            'https://api.binance.com/api/v3/klines',
            {'symbol': pair, 'interval': '1d', 'startTime': 0, 'limit': 100},
        )
        if not data:
            return None
        for candle in data:
            if float(candle[5]) > 0 or float(candle[1]) > 0:
                return datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
        return None

    async def _kraken(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}{quote}'
        data = await self._get(
            'https://api.kraken.com/0/public/OHLC',
            {'pair': pair, 'interval': 1440},
        )
        if not data or data.get('error'):
            if base == 'BTC':
                data = await self._get(
                    'https://api.kraken.com/0/public/OHLC',
                    {'pair': f'XBT{quote}', 'interval': 1440},
                )
            if not data:
                return None
        result = data.get('result', {})
        for key, candles in result.items():
            if key == 'last':
                continue
            if candles:
                return datetime.fromtimestamp(candles[0][0], tz=timezone.utc)
        return None

    async def _bitstamp(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}{quote}'.lower()
        data = await self._get(
            f'https://www.bitstamp.net/api/v2/ohlc/{pair}/',
            {'step': 86400, 'limit': 100, 'start': 0},
        )
        if not data:
            return None
        ohlc = data.get('data', {}).get('ohlc', [])
        for candle in ohlc:
            if float(candle.get('volume', 0)) > 0 or float(candle.get('open', 0)) > 0:
                return datetime.fromtimestamp(int(candle['timestamp']), tz=timezone.utc)
        return None

    async def _coinbase(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}-{quote}'
        data = await self._get(
            f'https://api.exchange.coinbase.com/products/{pair}/candles',
            {'granularity': 86400},
        )
        if not data:
            return None
        for candle in reversed(data):
            if len(candle) >= 5 and (float(candle[5]) > 0 or float(candle[1]) > 0):
                return datetime.fromtimestamp(candle[0], tz=timezone.utc)
        return None

    async def _bitfinex(self, base: str, quote: str) -> datetime | None:
        pair = f't{base}{quote}'
        data = await self._get(
            f'https://api-pub.bitfinex.com/v2/candles/trade:1d:{pair}/hist',
            {'limit': 100, 'sort': 1},
        )
        if not data:
            return None
        for candle in data:
            if len(candle) >= 6 and (candle[5] or candle[1]):
                return datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
        return None

    async def _poloniex(self, base: str, quote: str) -> datetime | None:
        pair = f'{quote}_{base}'
        data = await self._get(
            f'https://api.poloniex.com/markets/{pair}/candles',
            {'interval': 'DAY_1', 'limit': 100},
        )
        if data and isinstance(data, list) and data:
            for candle in data:
                if float(candle.get('volume', 0)) > 0 or float(candle.get('open', 0)) > 0:
                    try:
                        return datetime.fromisoformat(candle['startTime'].replace('Z', '+00:00'))
                    except (ValueError, KeyError):
                        pass
            return datetime.fromisoformat(data[0]['startTime'].replace('Z', '+00:00'))
        return None

    async def _bittrex(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}-{quote}'
        data = await self._get(
            f'https://api.bittrex.com/v3/markets/{pair}/candles',
            {'candleType': 'TRADE', 'granularity': 'DAY_1'},
        )
        if not data:
            return None
        for candle in data:
            if float(candle.get('volume', 0)) > 0 or float(candle.get('open', 0)) > 0:
                try:
                    return datetime.fromisoformat(candle['startsAt'].replace('Z', '+00:00'))
                except (ValueError, KeyError):
                    pass
        return None

    async def _bybit(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}{quote}'
        data = await self._get(
            'https://api.bybit.com/v5/market/kline',
            {'category': 'spot', 'symbol': pair, 'interval': 'D', 'limit': 1},
        )
        if data and data.get('retCode') == 0:
            lst = data.get('result', {}).get('list', [])
            if lst:
                return datetime.fromtimestamp(int(lst[0][0]) / 1000, tz=timezone.utc)
        return None

    async def _okx(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}-{quote}'
        data = await self._get(
            'https://www.okx.com/api/v5/market/history-candles',
            {'instId': pair, 'bar': '1day', 'limit': 1},
        )
        if data and data.get('code') == '0':
            candles = data.get('data', [])
            if candles:
                return datetime.fromtimestamp(int(candles[0][0]) / 1000, tz=timezone.utc)
        return None

    async def _gateio(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}_{quote}'
        data = await self._get(
            'https://api.gateio.ws/api/v4/spot/candlesticks',
            {'currency_pair': pair, 'interval': '1d', 'limit': 1},
        )
        if data and len(data) > 0:
            return datetime.fromtimestamp(int(data[0][0]), tz=timezone.utc)
        return None

    async def _htx(self, base: str, quote: str) -> datetime | None:
        pair = f'{base.lower()}{quote.lower()}'
        data = await self._get(
            'https://api.huobi.pro/market/history/kline',
            {'symbol': pair, 'period': '1day', 'size': 1},
        )
        if data and data.get('status') == 'ok':
            klines = data.get('data', [])
            if klines:
                return datetime.fromtimestamp(klines[0]['id'], tz=timezone.utc)
        return None

    async def _mexc(self, base: str, quote: str) -> datetime | None:
        pair = f'{base}{quote}'
        data = await self._get(
            'https://api.mexc.com/api/v3/klines',
            {'symbol': pair, 'interval': '1d', 'limit': 1, 'startTime': 0},
        )
        if data and len(data) > 0:
            return datetime.fromtimestamp(data[0][0] / 1000, tz=timezone.utc)
        return None
