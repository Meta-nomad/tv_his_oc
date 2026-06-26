"""
CoinGecko API service.
Resolves ticker -> coin_id and fetches exchange tickers.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp

from config import COINGECKO_BASE_URL

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "TradingViewHistoryBot/1.0",
}

# Rate limit: CoinGecko free tier ~30 req/min
_REQUEST_DELAY = 1.2  # seconds between requests


async def _get(session: aiohttp.ClientSession, url: str, params: dict = None) -> Optional[dict | list]:
    try:
        async with session.get(url, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 429:
                logger.warning("CoinGecko rate limit hit, sleeping 10s")
                await asyncio.sleep(10)
                async with session.get(url, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp2:
                    if resp2.status != 200:
                        return None
                    return await resp2.json()
            if resp.status != 200:
                logger.warning("CoinGecko %s -> HTTP %s", url, resp.status)
                return None
            return await resp.json()
    except Exception as e:
        logger.error("CoinGecko request error: %s", e)
        return None


async def search_coin_id(session: aiohttp.ClientSession, ticker: str) -> Optional[str]:
    """
    Find CoinGecko coin_id by ticker symbol.
    Returns the best match coin_id or None.
    """
    url = f"{COINGECKO_BASE_URL}/search"
    data = await _get(session, url, {"query": ticker})
    if not data or "coins" not in data:
        return None

    coins = data["coins"]
    ticker_upper = ticker.upper()

    # Exact symbol match
    for coin in coins:
        if coin.get("symbol", "").upper() == ticker_upper:
            return coin["id"]

    return None


async def get_coin_details(session: aiohttp.ClientSession, coin_id: str) -> Optional[dict]:
    """Get full coin details including genesis date."""
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "false",
        "community_data": "false",
        "developer_data": "false",
    }
    return await _get(session, url, params)


async def get_coin_tickers(session: aiohttp.ClientSession, coin_id: str) -> list[dict]:
    """
    Fetch all exchange tickers for a coin from CoinGecko (paginated).
    Returns list of ticker dicts with exchange info.
    """
    all_tickers = []
    page = 1
    while True:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/tickers"
        params = {"page": page, "per_page": 100, "include_exchange_logo": "false", "depth": "false"}
        data = await _get(session, url, params)
        if not data or "tickers" not in data:
            break
        tickers = data["tickers"]
        if not tickers:
            break
        all_tickers.extend(tickers)
        # CoinGecko returns max 100 per page; if we got less, we're done
        if len(tickers) < 100:
            break
        page += 1
        await asyncio.sleep(_REQUEST_DELAY)

    return all_tickers


async def get_earliest_date_from_market_chart(
    session: aiohttp.ClientSession, coin_id: str
) -> Optional[str]:
    """
    Get earliest available price date from CoinGecko market chart (max history).
    """
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "max", "interval": "daily"}
    data = await _get(session, url, params)
    if not data or "prices" not in data or not data["prices"]:
        return None

    earliest_ts = data["prices"][0][0]  # milliseconds
    dt = datetime.utcfromtimestamp(earliest_ts / 1000)
    return dt.strftime("%Y-%m-%d")
