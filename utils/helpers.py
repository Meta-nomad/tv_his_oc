from config.settings import EXCHANGE_TV_MAP
import urllib.parse


def normalize_exchange(exchange_id: str) -> str:
    """Normalize exchange id to TradingView prefix."""
    key = exchange_id.lower().replace("-", "").replace("_", "").replace(" ", "")
    return EXCHANGE_TV_MAP.get(key, exchange_id.upper())


def build_tv_symbol(exchange_tv: str, base: str, quote: str) -> str:
    """Build TradingView symbol string."""
    return f"{exchange_tv}:{base}{quote}"


def build_tv_url(symbol: str) -> str:
    """Build TradingView chart URL."""
    encoded = urllib.parse.quote(symbol, safe="")
    return f"https://www.tradingview.com/chart/?symbol={encoded}"
