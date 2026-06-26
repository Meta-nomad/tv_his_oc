from urllib.parse import quote
from datetime import datetime

EXCHANGE_DISPLAY_NAMES = {
    'kraken': 'Kraken',
    'bitfinex': 'Bitfinex',
    'coinbase': 'Coinbase',
    'coinbasepro': 'Coinbase',
    'poloniex': 'Poloniex',
    'bittrex': 'Bittrex',
    'bitstamp': 'Bitstamp',
    'binance': 'Binance',
    'bybit': 'Bybit',
    'okx': 'OKX',
    'kucoin': 'KuCoin',
    'gateio': 'Gate.io',
    'gate': 'Gate.io',
    'htx': 'HTX',
    'huobi': 'HTX',
    'huobiglobal': 'HTX',
    'mexc': 'MEXC',
    'gemini': 'Gemini',
    'cryptocom': 'Crypto.com',
    'crypto.com': 'Crypto.com',
}

EXCHANGE_LAUNCH_DATES = {
    'kraken': datetime(2011, 9, 13),
    'bitstamp': datetime(2011, 8, 18),
    'coinbase': datetime(2012, 6, 20),
    'coinbasepro': datetime(2012, 6, 20),
    'bitfinex': datetime(2012, 12, 1),
    'gateio': datetime(2013, 1, 1),
    'gate': datetime(2013, 1, 1),
    'htx': datetime(2013, 9, 1),
    'huobi': datetime(2013, 9, 1),
    'huobiglobal': datetime(2013, 9, 1),
    'poloniex': datetime(2014, 1, 1),
    'bittrex': datetime(2014, 2, 1),
    'okx': datetime(2014, 1, 1),
    'gemini': datetime(2015, 10, 1),
    'binance': datetime(2017, 7, 14),
    'kucoin': datetime(2017, 9, 1),
    'mexc': datetime(2018, 4, 1),
    'bybit': datetime(2018, 3, 1),
    'cryptocom': datetime(2018, 11, 1),
}


def get_exchange_display_name(name: str) -> str:
    key = name.lower().strip().replace(' ', '').replace('-', '')
    direct = EXCHANGE_DISPLAY_NAMES.get(key)
    if direct:
        return direct
    for k, v in EXCHANGE_DISPLAY_NAMES.items():
        if k in key or key.replace('_', '') in k:
            return v
    return name.title()


def get_exchange_launch_date(name: str) -> datetime | None:
    key = name.lower().strip().replace(' ', '').replace('-', '')
    direct = EXCHANGE_LAUNCH_DATES.get(key)
    if direct:
        return direct
    for k, v in EXCHANGE_LAUNCH_DATES.items():
        if k in key or key.replace('_', '') in k:
            return v
    return None


def build_tradingview_symbol(exchange: str, base: str, quote: str) -> str:
    return f"{exchange.upper()}:{base.upper()}{quote.upper()}"


def build_tradingview_url(symbol: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol={quote(symbol, safe='')}"


def format_date(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d')
