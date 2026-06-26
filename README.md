# TradingView History Bot

Telegram-бот, который по тикеру криптовалюты определяет биржу с **самой длинной** доступной историей цены для TradingView.

---

## Как работает

1. Пользователь отправляет тикер (напр. `ZEC`)
2. Бот находит монету через **CoinGecko API**
3. Получает список всех бирж, на которых торгуется монета
4. Для каждой биржи запрашивает исторические данные через **CryptoCompare API**
5. Сортирует по дате начала истории
6. Возвращает оптимальный TradingView символ и прямую ссылку

Результаты кэшируются на **24 часа**.

---

## Требования

- Python 3.12+
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))
- CryptoCompare API Key (бесплатный на [cryptocompare.com](https://www.cryptocompare.com/cryptopian/api-keys)) — опционально, без него работает с более низкими лимитами

---

## Установка и запуск

### 1. Клонировать / распаковать проект

```bash
cd tgbot
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Создать `.env` файл

```bash
cp .env.example .env
```

Открыть `.env` и заполнить:

```env
TELEGRAM_BOT_TOKEN=123456789:AABBCCDDEEFFaabbccddeeff...
CRYPTOCOMPARE_API_KEY=your_key_here   # можно оставить пустым
```

### 5. Запустить бота

```bash
python main.py
```

---

## Структура проекта

```
tgbot/
├── main.py                  # Точка входа
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py
│   └── settings.py          # Настройки из .env
├── bot/
│   ├── __init__.py
│   └── handlers.py          # Telegram handlers (aiogram)
├── services/
│   ├── __init__.py
│   ├── analyzer.py          # Основная логика анализа
│   ├── coingecko.py         # CoinGecko API
│   └── cryptocompare.py     # CryptoCompare API
└── utils/
    ├── __init__.py
    ├── cache.py             # In-memory кэш (24h TTL)
    └── helpers.py           # Форматирование символов и URL
```

---

## Пример ответа

```
📊 Монета: ZEC

✅ Рекомендуемый символ TradingView:
KRAKEN:ZECUSD

🏦 Биржа: KRAKEN

📅 Дата начала истории: 2016-10-29

🔗 Ссылка:
https://www.tradingview.com/chart/?symbol=KRAKEN%3AZECUSD

📋 Альтернативы:
• BITFINEX:ZECUSD
• COINBASE:ZECUSD
```

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Инструкция по использованию |
| `/help` | То же самое |
| `BTC` | Любой тикер — анализ истории |

---

## Примечания

- CoinGecko бесплатный tier: ~30 запросов/мин. При высокой нагрузке добавьте задержки или используйте Pro API.
- CryptoCompare без ключа: 100,000 вызовов/месяц. С ключом — больше.
- Первый запрос по новому тикеру может занять 10–30 секунд (опрос нескольких API).
- Повторные запросы того же тикера отвечают мгновенно (из кэша).
