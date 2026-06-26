import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
CRYPTOCOMPARE_API_KEY: str = os.getenv("CRYPTOCOMPARE_API_KEY", "")

CACHE_TTL_SECONDS: int = 86400  # 24 hours

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
CRYPTOCOMPARE_BASE_URL = "https://min-api.cryptocompare.com/data"

# TradingView exchange name mapping
EXCHANGE_TV_MAP: dict[str, str] = {
    "kraken": "KRAKEN",
    "bitfinex": "BITFINEX",
    "coinbase": "COINBASE",
    "coinbasepro": "COINBASE",
    "gdax": "COINBASE",
    "poloniex": "POLONIEX",
    "bittrex": "BITTREX",
    "bitstamp": "BITSTAMP",
    "binance": "BINANCE",
    "bybit": "BYBIT",
    "okx": "OKX",
    "okex": "OKX",
    "kucoin": "KUCOIN",
    "gateio": "GATEIO",
    "gate": "GATEIO",
    "huobi": "HTX",
    "htx": "HTX",
    "mexc": "MEXC",
    "gemini": "GEMINI",
    "bitbay": "BITBAY",
    "bitmex": "BITMEX",
    "liquid": "LIQUID",
    "ftx": "FTX",
}

# USDT was created in October 2014. For coins older than this date,
# we search USD pairs first (they have earlier history).
# For newer coins, USDT is the default priority.
USDT_LAUNCH_DATE = "2014-10-06"

# Quote priority when coin predates USDT (USD history goes further back)
QUOTE_PRIORITY_OLD_COIN = ["USD", "BTC", "ETH", "USDT", "USDC", "BUSD"]

# Quote priority for coins born after USDT launch (USDT pairs are the standard)
QUOTE_PRIORITY_NEW_COIN = ["USDT", "USD", "BUSD", "USDC", "BTC", "ETH"]
