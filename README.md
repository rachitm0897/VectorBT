# VectorBT Strategy Lab

Minimal full-stack MVP for deterministic VectorBT backtests using Finnhub daily OHLCV candles.

This MVP includes a Django + Django REST Framework backend, a Vite + React + TypeScript frontend, LangGraph request parsing, VectorBT backtests, Monte Carlo simulation, and a separate Metabase analytics layer. It intentionally does not include auth, broker integration, WebSockets, Celery, Redis, intraday data, or live trading. OHLCV data is only fetched from Finnhub and is not sent to any LLM.

## Environment

Create a `.env` file in the repo root:

```env
FINNHUB_API_KEY=your_finnhub_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
DJANGO_SECRET_KEY=change-me-for-local-dev
VITE_API_BASE_URL=http://localhost:8000
ANALYTICS_DB_NAME=analytics
ANALYTICS_DB_USER=analytics_user
ANALYTICS_DB_PASSWORD=analytics_password
ANALYTICS_DB_HOST=analytics_db
ANALYTICS_DB_PORT=5432
ANALYTICS_ENABLED=true
METABASE_URL=http://localhost:3000
```

## Run Full App With Docker

```bash
docker compose up --build
```

The app will be available at:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
Metabase: http://localhost:3000
```

Use the left form panel to run `AAPL` with `SMA crossover`, or switch to `RSI mean reversion` and edit the parameters JSON.

## Metabase Analytics Layer

Metabase reads stored analytics summaries from the separate `analytics_db` PostgreSQL database and creates internal dashboards.

It does not run backtests. It does not replace the React dashboard. It does not call the LLM. If analytics persistence fails, the backtest response should still succeed.

Start the full stack:

```bash
docker compose up --build
```

Initialize analytics tables:

```bash
docker compose exec backend python manage.py init_analytics_db
```

Seed demo analytics data:

```bash
docker compose exec backend python manage.py seed_analytics_demo
```

Open Metabase:

```text
http://localhost:3000
```

Connect Metabase to `analytics_db`:

```text
Database type: PostgreSQL
Host: analytics_db
Port: 5432
Database name: analytics
Username: analytics_user
Password: analytics_password
```

Inside Docker Compose, use host `analytics_db`, not `localhost`.

Suggested dashboards:

- Backtest Overview
- Strategy Comparison
- Symbol Performance
- Token Usage
- Data Quality
- Trade Analysis

Strategy comparison:

```sql
SELECT
    strategy,
    COUNT(*) AS runs,
    AVG(total_return_pct) AS avg_return,
    AVG(sharpe_ratio) AS avg_sharpe,
    AVG(max_drawdown_pct) AS avg_drawdown,
    AVG(win_rate_pct) AS avg_win_rate
FROM backtest_runs
WHERE status = 'success'
GROUP BY strategy
ORDER BY avg_sharpe DESC;
```

Best backtests:

```sql
SELECT
    created_at,
    symbol,
    strategy,
    total_return_pct,
    sharpe_ratio,
    max_drawdown_pct,
    win_rate_pct,
    total_trades
FROM backtest_runs
WHERE status = 'success'
ORDER BY sharpe_ratio DESC
LIMIT 20;
```

Token usage:

```sql
SELECT
    DATE(created_at) AS date,
    SUM(llm_calls) AS total_llm_calls,
    SUM(COALESCE(estimated_prompt_tokens, 0) + COALESCE(estimated_output_tokens, 0)) AS estimated_tokens,
    COUNT(*) FILTER (WHERE parser_cache = 'HIT') AS cache_hits,
    COUNT(*) FILTER (WHERE parser_cache = 'MISS') AS cache_misses
FROM backtest_runs
GROUP BY DATE(created_at)
ORDER BY date;
```

Data quality:

```sql
SELECT
    symbol,
    COUNT(*) AS runs,
    AVG(candles_fetched) AS avg_candles,
    COUNT(*) FILTER (WHERE cache_status = 'HIT') AS cache_hits,
    COUNT(*) FILTER (WHERE status = 'error') AS errors
FROM backtest_runs
GROUP BY symbol
ORDER BY errors DESC;
```

Trade analysis:

```sql
SELECT
    strategy,
    COUNT(*) AS trades,
    AVG(return_pct) AS avg_trade_return,
    AVG(duration_days) AS avg_duration_days,
    SUM(pnl) AS total_pnl
FROM backtest_trades
GROUP BY strategy
ORDER BY total_pnl DESC;
```

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
- SQLite is used only for Django's default local setup.
- Analytics summaries are persisted separately to `analytics_db` for Metabase reporting only.
