"""
CryptoCompare API service.
Used to determine the earliest available OHLCV data per exchange
and to score hourly chart continuity (gap ratio).
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp

from config import CRYPTOCOMPARE_BASE_URL, CRYPTOCOMPARE_API_KEY

logger = logging.getLogger(__name__)

# How many recent hourly candles to fetch for gap analysis.
# 2000 hours ≈ 83 days — enough to get a solid continuity score.
HOURLY_SAMPLE_SIZE = 2000


def _headers() -> dict:
    h = {"Accept": "application/json", "User-Agent": "TradingViewHistoryBot/1.0"}
    if CRYPTOCOMPARE_API_KEY:
        h["authorization"] = f"Apikey {CRYPTOCOMPARE_API_KEY}"
    return h


async def _get(session: aiohttp.ClientSession, url: str, params: dict = None) -> Optional[dict]:
    try:
        async with session.get(
            url, params=params, headers=_headers(), timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            if resp.status != 200:
                logger.warning("CryptoCompare %s -> HTTP %s", url, resp.status)
                return None
            data = await resp.json()
            if data.get("Response") == "Error":
                logger.debug("CryptoCompare error: %s", data.get("Message"))
                return None
            return data
    except Exception as e:
        logger.error("CryptoCompare request error: %s", e)
        return None


async def get_all_history_alldata(
    session: aiohttp.ClientSession, base: str, quote: str, exchange: str
) -> Optional[datetime]:
    """
    Fetch full daily history with allData=true, return earliest valid date.
    A bar is considered valid if it has non-zero volume.
    """
    url = f"{CRYPTOCOMPARE_BASE_URL}/v2/histoday"
    params = {
        "fsym": base.upper(),
        "tsym": quote.upper(),
        "e": exchange,
        "limit": 2000,
        "allData": "true",
    }
    data = await _get(session, url, params)
    if not data or "Data" not in data or "Data" not in data["Data"]:
        return None

    bars = data["Data"]["Data"]
    if not bars:
        return None

    for bar in bars:
        if (bar.get("volumefrom", 0) > 0 or bar.get("volumeto", 0) > 0) and bar.get("time", 0) > 0:
            return datetime.fromtimestamp(bar["time"], tz=timezone.utc)

    return None


def _count_hourly_gaps(bars: list[dict]) -> tuple[int, int]:
    """
    Given a list of hourly bars (each with a 'time' unix timestamp),
    count how many expected 1-hour slots are missing.

    Returns (gap_count, expected_total).

    A 'gap' is any slot between consecutive bars where the timestamp
    jump is more than 1 hour (3600 seconds). We also count zero-volume
    bars as soft gaps (weighted 0.5) to penalise dead periods.
    """
    if len(bars) < 2:
        return 0, 1

    # Filter to bars with actual timestamps
    times = sorted(b["time"] for b in bars if b.get("time", 0) > 0)
    if len(times) < 2:
        return 0, 1

    first_ts = times[0]
    last_ts = times[-1]
    expected_slots = max(1, (last_ts - first_ts) // 3600)

    # Count hard gaps: consecutive timestamps differ by > 1 hour
    hard_gaps = 0
    for i in range(1, len(times)):
        diff_hours = (times[i] - times[i - 1]) / 3600
        if diff_hours > 1.5:  # allow small rounding
            # Each missing hour counts as one gap slot
            hard_gaps += int(diff_hours) - 1

    # Count zero-volume bars as soft gaps (each counts as 0.5 of a gap)
    zero_vol_count = sum(
        1 for b in bars
        if b.get("volumefrom", 0) == 0 and b.get("volumeto", 0) == 0
    )
    soft_gap_contribution = zero_vol_count * 0.5

    total_gaps = hard_gaps + soft_gap_contribution
    return total_gaps, expected_slots


async def get_hourly_gap_score(
    session: aiohttp.ClientSession, base: str, quote: str, exchange: str
) -> float:
    """
    Fetch the most recent HOURLY_SAMPLE_SIZE hourly candles for a pair on an exchange
    and return a gap_ratio in [0.0, 1.0]:

        gap_ratio = gaps / expected_slots

    0.0 = perfect, no gaps at all.
    1.0 = completely discontinuous data.

    Returns 1.0 (worst possible) if data cannot be fetched, so
    exchanges with missing hourly data are naturally deprioritised.
    """
    url = f"{CRYPTOCOMPARE_BASE_URL}/v2/histohour"
    params = {
        "fsym": base.upper(),
        "tsym": quote.upper(),
        "e": exchange,
        "limit": HOURLY_SAMPLE_SIZE,
    }
    data = await _get(session, url, params)
    if not data or "Data" not in data or "Data" not in data["Data"]:
        logger.debug("No hourly data for %s/%s on %s", base, quote, exchange)
        return 1.0

    bars = data["Data"]["Data"]
    if not bars:
        return 1.0

    gaps, expected = _count_hourly_gaps(bars)
    if expected == 0:
        return 1.0

    ratio = gaps / expected
    ratio = min(ratio, 1.0)  # clamp to [0, 1]
    logger.debug(
        "Hourly gap score for %s/%s on %s: %.4f (gaps=%s, expected=%d)",
        base, quote, exchange, ratio, gaps, expected,
    )
    return ratio
