import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY', '')
CACHE_TTL = int(os.getenv('CACHE_TTL', '86400'))


class Settings:
    def __init__(self):
        self.BOT_TOKEN = BOT_TOKEN
        self.CRYPTOCOMPARE_API_KEY = CRYPTOCOMPARE_API_KEY
        self.CACHE_TTL = CACHE_TTL


def get_settings() -> Settings:
    return Settings()
