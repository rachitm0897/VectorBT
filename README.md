# VectorBT Backtesting Sandbox Backend

Minimal Django + Django REST Framework backend for deterministic VectorBT backtests using Finnhub daily OHLCV candles.

This MVP intentionally does not include LangGraph, React, auth, broker integration, Celery, Redis, PostgreSQL, intraday data, or live trading. OHLCV data is only fetched from Finnhub and is not sent to any LLM.

## Environment

Create a `.env` file in the repo root:

```env
FINNHUB_API_KEY=your_finnhub_api_key
DJANGO_SECRET_KEY=change-me-for-local-dev
```

## Run With Docker

```bash
docker compose up --build
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

## Run Locally

VectorBT dependencies are most reliable on Python 3.11.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

On macOS/Linux, activate with:

```bash
source .venv/bin/activate
```

## Test The Backtest Endpoint

SMA crossover for Apple:

```bash
curl -X POST http://127.0.0.1:8000/api/backtest/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy": "sma_crossover",
    "parameters": {
      "fast_window": 20,
      "slow_window": 50
    },
    "lookback": "2y",
    "resolution": "D",
    "initial_cash": 10000,
    "fees": 0.001,
    "monte_carlo": {
      "enabled": true,
      "days": 60,
      "simulations": 500,
      "method": "bootstrap"
    }
  }'
```

RSI mean reversion for Nvidia:

```bash
curl -X POST http://127.0.0.1:8000/api/backtest/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NVDA",
    "strategy": "rsi_mean_reversion",
    "parameters": {
      "rsi_window": 14,
      "lower": 30,
      "upper": 70
    },
    "lookback": "2y",
    "resolution": "D",
    "initial_cash": 10000,
    "fees": 0.001,
    "monte_carlo": {
      "enabled": true,
      "days": 60,
      "simulations": 500,
      "method": "bootstrap"
    }
  }'
```

PowerShell users should call `curl.exe` and escape JSON quotes if using `-d` inline.

## Notes

- Only daily candles are supported.
- Finnhub responses are cached under `backend/cache/market_data/`.
- Cache keys include symbol, resolution, start timestamp, and end timestamp.
- SQLite is used only for Django's default local setup. Backtest results are not persisted.
