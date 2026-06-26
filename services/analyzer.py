import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from services.coingecko import CoinGeckoService
from services.cryptocompare import CryptoCompareService
from services.exchange_api import ExchangeAPIService
from utils.helpers import (
    get_exchange_display_name,
    get_exchange_launch_date,
    normalize_exchange_key,
    build_tradingview_symbol,
    build_tradingview_url,
    format_date,
)

USDT_CREATION = datetime(2014, 10, 6, tzinfo=timezone.utc)

logger = logging.getLogger(__name__)


class AnalysisResult:
    def __init__(
        self,
        coin_name: str,
        coin_symbol: str,
        best_exchange: str,
        best_pair: str,
        best_date: datetime,
        quote: str,
        alternatives: list[dict[str, Any]],
        genesis_date: datetime | None = None,
    ):
        self.coin_name = coin_name
        self.coin_symbol = coin_symbol
        self.best_exchange = best_exchange
        self.best_pair = best_pair
        self.best_date = best_date
        self.quote = quote
        self.alternatives = alternatives
        self.genesis_date = genesis_date

    def to_message(self) -> str:
        lines = [
            f"Монета: {self.coin_symbol}",
            "",
            "Лучший график:",
            self.best_pair,
            "",
            "Биржа:",
            self.best_exchange,
            "",
            "История с:",
            format_date(self.best_date),
            "",
            "Ссылка TradingView:",
            build_tradingview_url(self.best_pair),
        ]
        if self.alternatives:
            lines.append("")
            lines.append("Альтернативы:")
            for alt in self.alternatives[:3]:
                lines.append(alt['pair'])
        return "\n".join(lines)


class Analyzer:
    def __init__(
        self,
        coingecko: CoinGeckoService,
        cryptocompare: CryptoCompareService,
        exchange_api: ExchangeAPIService,
        cache,
    ):
        self.coingecko = coingecko
        self.cryptocompare = cryptocompare
        self.exchange_api = exchange_api
        self.cache = cache

    async def analyze(self, ticker: str) -> AnalysisResult | None:
        ticker = ticker.strip().upper()
        cache_key = f'analysis_v2_{ticker}'
        cached = self.cache.get(cache_key)
        if cached:
            return self._from_dict(cached)

        coin_info = await self.coingecko.resolve_coin(ticker)
        if not coin_info:
            return None

        coin_name = coin_info.get('name', ticker)
        coin_id = coin_info.get('id', '')

        genesis_date = None
        gd_str = coin_info.get('genesis_date')
        if gd_str:
            try:
                genesis_date = datetime.strptime(gd_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        tickers = await self.coingecko.get_coin_tickers(coin_id)
        if not tickers:
            return None

        exchange_pairs: dict[str, dict[tuple[str, str], float]] = {}
        for t in tickers:
            market = t.get('market', {}) or {}
            ex_name = (market.get('identifier') or market.get('name', '')).lower().strip()
            base = (t.get('base') or '').upper()
            quote = (t.get('target') or '').upper()
            vol = float(t.get('volume', 0) or 0)
            if not ex_name or base != ticker or not quote:
                continue
            ex_key = normalize_exchange_key(ex_name)
            if not ex_key:
                ex_key = ex_name
            exchange_pairs.setdefault(ex_key, {})
            key = (base, quote)
            exchange_pairs[ex_key][key] = max(exchange_pairs[ex_key].get(key, 0), vol)

        predates_usdt = genesis_date is not None and genesis_date < USDT_CREATION
        search_quotes = ['USD', 'USDC', 'USDT'] if predates_usdt else ['USDT', 'USD', 'USDC']

        exchange_data = []
        for sq in search_quotes:
            tasks: list[asyncio.Task] = []
            for exchange, pairs in exchange_pairs.items():
                if (ticker, sq) not in pairs:
                    continue
                task = asyncio.ensure_future(
                    self._evaluate(exchange, ticker, sq, pairs)
                )
                tasks.append(task)
            if tasks:
                results = await asyncio.gather(*tasks)
                exchange_data = [r for r in results if r is not None]
                if exchange_data:
                    # Нашли биржи с этой квотой — берём лучшую по дате и выходим
                    exchange_data.sort(key=lambda x: (x['date'], -x.get('volume', 0)))
                    break

        if not exchange_data:
            logger.warning('No exchange data found for %s', ticker)
            return None

        best = exchange_data[0]
        tied = [r for r in exchange_data if abs((r['date'] - best['date']).total_seconds()) < 86400]

        if len(tied) > 1:
            cont_tasks = [
                asyncio.ensure_future(
                    self.cryptocompare.check_continuity(ticker, r['quote'], r['exchange'])
                )
                for r in tied
            ]
            cont_results = await asyncio.gather(*cont_tasks)

            for r, (gaps, avg_vol) in zip(tied, cont_results):
                r['cont_score'] = gaps
                r['avg_volume'] = avg_vol

            tied.sort(key=lambda x: (x.get('cont_score', 999), -x.get('avg_volume', 0)))
            if tied[0] != best:
                logger.info(
                    'Better continuity found for %s: %s (%d gaps) vs %s (%d gaps)',
                    ticker, tied[0]['exchange'], tied[0].get('cont_score', 999),
                    best['exchange'], best.get('cont_score', 999),
                )
            best = tied[0]

        display_name = get_exchange_display_name(best['exchange'])
        if display_name == best['exchange'].title():
            display_name = best['exchange'].upper() if best['exchange'] == best['exchange'].upper() else best['exchange'].title()

        ex_raw = best['exchange'].upper().replace(' ', '')
        best_pair = build_tradingview_symbol(ex_raw, ticker, best['quote'])

        alternatives = []
        for r in exchange_data[1:4]:
            alt_ex_raw = r['exchange'].upper().replace(' ', '')
            alt_pair = build_tradingview_symbol(alt_ex_raw, ticker, r['quote'])
            alternatives.append({
                'pair': alt_pair,
                'exchange': get_exchange_display_name(r['exchange']),
                'date': r['date'].isoformat(),
            })

        result = AnalysisResult(
            coin_name=coin_name,
            coin_symbol=ticker,
            best_exchange=display_name,
            best_pair=best_pair,
            best_date=best['date'],
            quote=best['quote'],
            alternatives=alternatives,
            genesis_date=genesis_date,
        )

        self.cache.set(cache_key, self._to_dict(result), ttl=86400)
        return result

    def _pick_quote(self, available: list[str], priority: list[str]) -> str | None:
        for q in priority:
            if q in available:
                return q
        for q in available:
            if q not in priority:
                return q
        return None

    async def _evaluate(self, exchange: str, base: str, quote: str, pairs: dict) -> dict | None:
        date = await self.exchange_api.get_earliest_date(exchange, base, quote)
        if not date:
            date = await self.cryptocompare.get_earliest_date(base, quote, exchange)
        if not date:
            date = await self.cryptocompare.get_earliest_date(base, quote, None)

        if date:
            launch = get_exchange_launch_date(exchange)
            if launch and date < launch:
                date = launch

            volume = pairs.get((base, quote), 0)
            return {
                'exchange': exchange,
                'quote': quote,
                'date': date,
                'volume': volume,
                'cont_score': 0,
                'avg_volume': 0.0,
            }
        return None

    def _to_dict(self, r: AnalysisResult) -> dict:
        return {
            'coin_name': r.coin_name,
            'coin_symbol': r.coin_symbol,
            'best_exchange': r.best_exchange,
            'best_pair': r.best_pair,
            'best_date': r.best_date.isoformat(),
            'quote': r.quote,
            'alternatives': r.alternatives,
            'genesis_date': r.genesis_date.isoformat() if r.genesis_date else None,
        }

    def _from_dict(self, d: dict) -> AnalysisResult:
        return AnalysisResult(
            coin_name=d['coin_name'],
            coin_symbol=d['coin_symbol'],
            best_exchange=d['best_exchange'],
            best_pair=d['best_pair'],
            best_date=datetime.fromisoformat(d['best_date']),
            quote=d['quote'],
            alternatives=d['alternatives'],
            genesis_date=datetime.fromisoformat(d['genesis_date']) if d.get('genesis_date') else None,
        )
