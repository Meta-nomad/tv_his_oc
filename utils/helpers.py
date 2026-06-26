from urllib.parse import quote
from datetime import datetime, timezone

EXCHANGE_DISPLAY_NAMES = {
    'kraken': 'Kraken',
    'bitfinex': 'Bitfinex',
    'coinbase': 'Coinbase',
    'coinbasepro': 'Coinbase',
    'gdax': 'Coinbase',
    'poloniex': 'Poloniex',
    'bittrex': 'Bittrex',
    'bitstamp': 'Bitstamp',
    'binance': 'Binance',
    'bybit': 'Bybit',
    'bybit_spot': 'Bybit',
    'okx': 'OKX',
    'okex': 'OKX',
    'kucoin': 'KuCoin',
    'gateio': 'Gate.io',
    'gate': 'Gate.io',
    'htx': 'HTX',
    'huobi': 'HTX',
    'huobiglobal': 'HTX',
    'mexc': 'MEXC',
    'mxc': 'MEXC',
    'gemini': 'Gemini',
    'cryptocom': 'Crypto.com',
}

EXCHANGE_NORMALIZE_MAP: dict[str, str] = {}
_EXCHANGE_NORMALIZE_RAW = {
    'gdax': 'coinbase',
    'coinbasepro': 'coinbase',
    'okex': 'okx',
    'bybit_spot': 'bybit',
    'bybit_lin': 'bybit',
    'bybit_inverse': 'bybit',
    'huobi': 'htx',
    'huobiglobal': 'htx',
    'huobipro': 'htx',
    'mxc': 'mexc',
    'gate': 'gateio',
}
for _k, _v in _EXCHANGE_NORMALIZE_RAW.items():
    EXCHANGE_NORMALIZE_MAP[_k.lower().replace('_', '').replace('-', '').replace(' ', '')] = _v


def _norm_key(s: str) -> str:
    return s.lower().strip().replace(' ', '').replace('-', '').replace('_', '')


def normalize_exchange_key(name: str) -> str:
    key = _norm_key(name)
    direct = EXCHANGE_NORMALIZE_MAP.get(key)
    if direct:
        return direct
    return key

EXCHANGE_LAUNCH_DATES = {
    'kraken': datetime(2011, 9, 13, tzinfo=timezone.utc),
    'bitstamp': datetime(2011, 8, 18, tzinfo=timezone.utc),
    'coinbase': datetime(2012, 6, 20, tzinfo=timezone.utc),
    'bitfinex': datetime(2012, 12, 1, tzinfo=timezone.utc),
    'gateio': datetime(2013, 1, 1, tzinfo=timezone.utc),
    'htx': datetime(2013, 9, 1, tzinfo=timezone.utc),
    'poloniex': datetime(2014, 1, 1, tzinfo=timezone.utc),
    'bittrex': datetime(2014, 2, 1, tzinfo=timezone.utc),
    'okx': datetime(2014, 1, 1, tzinfo=timezone.utc),
    'gemini': datetime(2015, 10, 1, tzinfo=timezone.utc),
    'binance': datetime(2017, 7, 14, tzinfo=timezone.utc),
    'kucoin': datetime(2017, 9, 1, tzinfo=timezone.utc),
    'mexc': datetime(2018, 4, 1, tzinfo=timezone.utc),
    'bybit': datetime(2018, 3, 1, tzinfo=timezone.utc),
    'cryptocom': datetime(2018, 11, 1, tzinfo=timezone.utc),
}


def get_exchange_display_name(name: str) -> str:
    key = name.lower().strip().replace(' ', '').replace('-', '')
    # Try direct match with display names
    for k, v in EXCHANGE_DISPLAY_NAMES.items():
        if k == key or f'_{k}' in key or k.replace('_', '') == key:
            return v
    # Try normalize then match
    nk = normalize_exchange_key(name)
    for k, v in EXCHANGE_DISPLAY_NAMES.items():
        if k == nk:
            return v
    return name.title()


def get_exchange_launch_date(name: str) -> datetime | None:
    nk = normalize_exchange_key(name)
    direct = EXCHANGE_LAUNCH_DATES.get(nk)
    if direct:
        return direct
    for k, v in EXCHANGE_LAUNCH_DATES.items():
        if k == nk or k in nk or nk in k:
            return v
    return None


def build_tradingview_symbol(exchange: str, base: str, quote: str) -> str:
    return f"{exchange.upper()}:{base.upper()}{quote.upper()}"


def build_tradingview_url(symbol: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol={quote(symbol, safe='')}"


def format_date(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d')
