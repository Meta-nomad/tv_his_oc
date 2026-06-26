"""
Core analysis service.
Determines the exchange with the earliest available price history for a given ticker.

Sorting priority:
  1. Earliest daily history date (primary — always wins)
  2. Hourly chart gap ratio (secondary — breaks ties between same-date exchanges)
  3. Quote currency priority (tertiary — last tiebreaker)

Quote currency selection:
  - Coin predates USDT (< 2014-10-06) → probe USD first, then BTC, ETH, USDT
  - Coin is newer → probe USDT first, then USD, BTC, ETH
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from typing import Optional

import aiohttp

from config import (
    CACHE_TTL_SECONDS,
    USDT_LAUNCH_DATE,
    QUOTE_PRIORITY_OLD_COIN,
    QUOTE_PRIORITY_NEW_COIN,
)
from services.coingecko import search_coin_id, get_coin_tickers, get_coin_details
from services.cryptocompare import get_all_history_alldata, get_hourly_gap_score
from utils.cache import cache_get, cache_set
from utils.helpers import normalize_exchange, build_tv_symbol, build_tv_url

logger = logging.getLogger(__name__)

_USDT_LAUNCH = date.fromisoformat(USDT_LAUNCH_DATE)

# Two exchanges are considered to have the "same" start date
# if they differ by at most this many days. Within this window,
# the hourly gap score becomes the deciding factor.
SAME_DATE_TOLERANCE_DAYS = 3


@dataclass
class ExchangeResult:
    exchange_id: str
    exchange_tv: str
    base: str
    quote: str
    earliest_date: datetime
    tv_symbol: str
    tv_url: str
    gap_ratio: float = 1.0          # 0.0 = perfect, 1.0 = worst
    gap_ratio_checked: bool = False  # False = not yet scored


@dataclass
class AnalysisResult:
    ticker: str
    best: ExchangeResult
    alternatives: list[ExchangeResult] = field(default_factory=list)


# ── Exchange name mapping ──────────────────────────────────────────────────────

def _cg_to_cc_exchange(exchange_id: str) -> str:
    """Map CoinGecko exchange identifier → CryptoCompare market name."""
    mapping = {
        "kraken": "Kraken",
        "bitfinex": "Bitfinex",
        "coinbase": "Coinbase",
        "gdax": "Coinbase",
        "coinbasepro": "Coinbase",
        "poloniex": "Poloniex",
        "bittrex": "Bittrex",
        "bitstamp": "Bitstamp",
        "binance": "Binance",
        "bybit": "Bybit",
        "okx": "OKEx",
        "okex": "OKEx",
        "kucoin": "Kucoin",
        "gate": "GateIO",
        "gateio": "GateIO",
        "huobi": "Huobi",
        "htx": "Huobi",
        "mexc": "MEXC",
        "gemini": "Gemini",
        "bitmex": "BitMEX",
        "ftx": "FTX",
        "liquid": "Liquid",
    }
    key = exchange_id.lower().replace("-", "").replace("_", "")
    return mapping.get(key, exchange_id.title())


# ── Quote currency helpers ────────────────────────────────────────────────────

def _coin_predates_usdt(genesis_date_str: Optional[str]) -> bool:
    if not genesis_date_str:
        return True  # unknown → treat as old, probe USD first
    try:
        return date.fromisoformat(genesis_date_str[:10]) < _USDT_LAUNCH
    except (ValueError, TypeError):
        return True


def _quote_priority(coin_is_old: bool) -> list[str]:
    return QUOTE_PRIORITY_OLD_COIN if coin_is_old else QUOTE_PRIORITY_NEW_COIN


# ── Gap scoring helpers ───────────────────────────────────────────────────────

def _same_date(a: datetime, b: datetime) -> bool:
    """True if two datetimes are within SAME_DATE_TOLERANCE_DAYS of each other."""
    return abs((a - b).days) <= SAME_DATE_TOLERANCE_DAYS


def _needs_gap_check(candidate: ExchangeResult, leader: ExchangeResult) -> bool:
    """
    Return True if candidate's start date is close enough to leader's
    that the hourly quality score should break the tie.
    """
    return _same_date(candidate.earliest_date, leader.earliest_date)


# ── Main analysis ─────────────────────────────────────────────────────────────

async def analyze_ticker(ticker: str) -> Optional[AnalysisResult]:
    ticker = ticker.strip().upper()

    cached = cache_get(f"analysis:{ticker}")
    if cached is not None:
        logger.info("Cache hit for %s", ticker)
        return cached

    async with aiohttp.ClientSession() as session:

        # 1. Resolve coin id
        coin_id = await search_coin_id(session, ticker)
        if not coin_id:
            logger.info("Coin not found: %s", ticker)
            return None
        logger.info("Resolved %s → %s", ticker, coin_id)

        # 2. Genesis date → quote priority
        details = await get_coin_details(session, coin_id)
        genesis_date: Optional[str] = details.get("genesis_date") if details else None
        logger.info("%s genesis_date=%s", ticker, genesis_date)

        coin_is_old = _coin_predates_usdt(genesis_date)
        q_priority = _quote_priority(coin_is_old)
        allowed_quotes = set(q_priority)
        logger.info("%s quote priority: %s", ticker, q_priority)

        # 3. Collect exchange tickers from CoinGecko
        cg_tickers = await get_coin_tickers(session, coin_id)
        if not cg_tickers:
            logger.warning("No CoinGecko tickers for %s", coin_id)
            return None

        # 4. Build unique (exchange, base, quote) candidates
        seen_keys: set[tuple[str, str]] = set()
        candidates: list[tuple[str, str, str]] = []
        for t in cg_tickers:
            base  = t.get("base", "").upper()
            quote = t.get("target", "").upper()
            ex    = t.get("market", {}).get("identifier", "")
            if base != ticker or not ex or quote not in allowed_quotes:
                continue
            k = (ex, quote)
            if k not in seen_keys:
                seen_keys.add(k)
                candidates.append((ex, base, quote))

        if not candidates:
            logger.warning("No relevant pairs for %s", ticker)
            return None
        logger.info("Probing %d candidates for %s", len(candidates), ticker)

        # 5. Fetch earliest daily date for every candidate (parallel, rate-limited)
        sem = asyncio.Semaphore(5)

        async def probe_daily(ex_id: str, base: str, quote: str):
            async with sem:
                cc = _cg_to_cc_exchange(ex_id)
                dt = await get_all_history_alldata(session, base, quote, cc)
                return ex_id, base, quote, dt

        daily_results = await asyncio.gather(
            *[probe_daily(ex, base, quote) for ex, base, quote in candidates]
        )

        # 6. Build ExchangeResult list (drop failures)
        results: list[ExchangeResult] = []
        for ex_id, base, quote, dt in daily_results:
            if dt is None:
                continue
            tv_ex  = normalize_exchange(ex_id)
            symbol = build_tv_symbol(tv_ex, base, quote)
            url    = build_tv_url(symbol)
            results.append(ExchangeResult(
                exchange_id=ex_id,
                exchange_tv=tv_ex,
                base=base,
                quote=quote,
                earliest_date=dt,
                tv_symbol=symbol,
                tv_url=url,
            ))

        if not results:
            logger.warning("No date data found for %s", ticker)
            return None

        # 7. Deduplicate per (exchange_tv, quote) keeping earliest date
        seen_dedup: dict[tuple[str, str], ExchangeResult] = {}
        for r in results:
            k = (r.exchange_tv, r.quote)
            if k not in seen_dedup or r.earliest_date < seen_dedup[k].earliest_date:
                seen_dedup[k] = r
        unique = list(seen_dedup.values())

        # 8. Find the absolute earliest date across all exchanges
        earliest_dt = min(r.earliest_date for r in unique)

        # 9. Identify all exchanges within SAME_DATE_TOLERANCE_DAYS of the leader
        #    → these need hourly gap scoring to break the tie
        tie_group = [r for r in unique if _same_date(r.earliest_date, earliest_dt)]
        non_tie   = [r for r in unique if not _same_date(r.earliest_date, earliest_dt)]

        logger.info(
            "%s: %d exchange(s) in tie group (within %d days of earliest %s)",
            ticker, len(tie_group), SAME_DATE_TOLERANCE_DAYS,
            earliest_dt.strftime("%Y-%m-%d"),
        )

        # 10. Fetch hourly gap scores only for the tie group (saves API calls)
        if len(tie_group) > 1:
            async def score_hourly(r: ExchangeResult) -> ExchangeResult:
                async with sem:
                    cc = _cg_to_cc_exchange(r.exchange_id)
                    ratio = await get_hourly_gap_score(session, r.base, r.quote, cc)
                    r.gap_ratio = ratio
                    r.gap_ratio_checked = True
                    return r

            tie_group = list(await asyncio.gather(*[score_hourly(r) for r in tie_group]))
            logger.info(
                "%s hourly gap scores: %s",
                ticker,
                [(r.tv_symbol, f"{r.gap_ratio:.4f}") for r in tie_group],
            )
        else:
            # Only one leader — still fetch its gap score so we can show it
            if tie_group:
                r = tie_group[0]
                async with sem:
                    cc = _cg_to_cc_exchange(r.exchange_id)
                    r.gap_ratio = await get_hourly_gap_score(session, r.base, r.quote, cc)
                    r.gap_ratio_checked = True

        # 11. Define final sort key:
        #       (earliest_date_bucket, gap_ratio, quote_rank)
        #     earliest_date_bucket: floor to day so ties within tolerance collapse
        def sort_key(r: ExchangeResult) -> tuple:
            # Bucket dates to the day (ignore sub-day differences)
            day_ts = r.earliest_date.replace(hour=0, minute=0, second=0, microsecond=0)
            q_rank = q_priority.index(r.quote) if r.quote in q_priority else 99
            gap    = r.gap_ratio if r.gap_ratio_checked else 0.5  # neutral default
            return (day_ts, gap, q_rank)

        tie_group.sort(key=sort_key)
        non_tie.sort(key=sort_key)

        ranked = tie_group + non_tie

        best = ranked[0]
        alternatives = [
            r for r in ranked[1:]
            if not (r.exchange_tv == best.exchange_tv and r.quote == best.quote)
        ][:4]

        result = AnalysisResult(ticker=ticker, best=best, alternatives=alternatives)
        cache_set(f"analysis:{ticker}", result, CACHE_TTL_SECONDS)
        return result
