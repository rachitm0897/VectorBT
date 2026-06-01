# VectorBT Strategy Lab

Minimal full-stack MVP for deterministic VectorBT backtests using Finnhub daily OHLCV candles.

This MVP includes a Django + Django REST Framework backend and a Vite + React + TypeScript frontend. It intentionally does not include LangGraph, auth, broker integration, WebSockets, Celery, Redis, PostgreSQL, intraday data, database persistence for backtests, or live trading. OHLCV data is only fetched from Finnhub and is not sent to any LLM.

## Environment

Create a `.env` file in the repo root:

```env
FINNHUB_API_KEY=your_finnhub_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
DJANGO_SECRET_KEY=change-me-for-local-dev
VITE_API_BASE_URL=http://localhost:8000
```

## Run Full App With Docker

```bash
docker compose up --build
```

The app will be available at:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
```

Use the left form panel to run `AAPL` with `SMA crossover`, or switch to `RSI mean reversion` and edit the parameters JSON.

## AI Chat Flow

The chat endpoint is deliberately token-minimal:

1. `parse_request_node` checks `backend/cache/parsed_requests/` by user-message hash. On a cache hit, it skips the LLM.
2. On a cache miss, the LLM receives only a compact parser prompt, supported strategies, defaults, ticker aliases, and the current user message.
3. `validate_request_node` fills defaults and validates the parsed JSON in Python.
4. `run_backtest_node` calls the existing deterministic VectorBT backtest function directly.
5. `format_response_node` creates a short template-based assistant message without a second LLM call.

The LLM never receives OHLCV arrays, equity curves, trades, Monte Carlo paths, raw VectorBT output, or previous chat history.

Chat endpoint:

```text
POST http://127.0.0.1:8000/api/chat/
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Backtest AAPL using RSI. Buy below 30 and sell above 70 for 2 years. Run Monte Carlo for 60 days."
  }'
```

Example chat prompts:

```text
Backtest Apple
Backtest NVDA using RSI, buy below 30 and sell above 70
Run Tesla with 10/50 moving average crossover for 1 year and simulate 90 days
Test MSFT with Bollinger bands, window 20 and 2 standard deviations
```

## Run Backend Locally

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

## Run Frontend Locally

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend reads `VITE_API_BASE_URL`, defaulting to `http://localhost:8000`.

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
- Parsed chat requests are cached under `backend/cache/parsed_requests/`.
- Cache keys include symbol, resolution, start timestamp, and end timestamp.
- SQLite is used only for Django's default local setup. Backtest results are not persisted.
