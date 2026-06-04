# VectorBT Strategy Lab Backend

Django + Django REST Framework backend for deterministic VectorBT strategy backtests and the AI chat parser.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Environment

Server-side fallback keys:

- `FINNHUB_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `PUBLIC_BACKEND_BASE_URL`
- `APP_BASE_PATH`
- `MCP_ENABLED`
- `MCP_TRANSPORT`
- `MCP_SERVER_URL`
- `MCP_CALL_TIMEOUT_SECONDS`
- `MCP_DEFAULT_TOOL`
- `MCP_ALLOWED_TOOLS`

The frontend can also send per-user keys on each request. These headers take precedence over the server-side fallback values:

- `X-OpenAI-API-Key`
- `X-Finnhub-API-Key`

## Run Locally

```bash
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

Health check:

```text
GET http://127.0.0.1:8000/api/health/live/
```

Backtest endpoint:

```text
POST http://127.0.0.1:8000/api/backtest/
```

Chat endpoint:

```text
POST http://127.0.0.1:8000/api/chat/
```

Portfolio optimizer endpoint:

```text
POST http://127.0.0.1:8000/api/portfolio/optimize/
```

Universe endpoints:

```text
GET http://127.0.0.1:8000/api/universe/sectors/
GET http://127.0.0.1:8000/api/universe/stocks/?sector=Technology
```

MCP status endpoint:

```text
GET http://127.0.0.1:8000/api/mcp/status/
GET http://127.0.0.1:8000/mcp/status/
```

## Docker

```bash
docker build -t vectorbt-backend:local .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env vectorbt-backend:local
```

For local compose:

```bash
docker compose -f docker-compose.dev.yml up --build
```

## QFS Platform

Use `https://qfsplatform.com/insta_backtester` as the QFS backend base URL. Deployment MCP settings:

```env
MCP_ENABLED=true
MCP_TRANSPORT=streamable_http
MCP_SERVER_URL=https://qfsplatform.com/insta_backtest_MCP_server/mcp
MCP_CALL_TIMEOUT_SECONDS=120
MCP_DEFAULT_TOOL=run_strategy_research
MCP_ALLOWED_TOOLS=run_strategy_research,run_markowitz_optimization,list_stock_universe,list_sectors,list_stocks_by_sector
```

The backend uses the user-provided OpenAI key for chat parsing and deterministically calls approved MCP tools only. Strategy backtests continue to call `run_strategy_research`. Portfolio optimization calls `run_markowitz_optimization`. Universe routes proxy `list_sectors` and `list_stocks_by_sector`. The backend passes the user-provided Finnhub key to market-data MCP tool arguments and does not include the OpenAI key in MCP calls.

The backend serves:

- `/insta_backtester_api/v1/backtest/`
- `/insta_backtester_api/v1/chat/`
- `/insta_backtester_api/v1/portfolio/optimize/`
- `/insta_backtester_api/v1/universe/sectors/`
- `/insta_backtester_api/v1/universe/stocks/`
- `/insta_backtester_api/v1/health/live/`
- `/insta_backtester/api/backtest/`
- `/insta_backtester/api/chat/`
- `/insta_backtester/api/portfolio/optimize/`
- `/insta_backtester/api/universe/sectors/`
- `/insta_backtester/api/universe/stocks/`
- `/insta_backtester/api/mcp/status/`
- `/insta_backtester/mcp/status/`
- `/mcp/status/`

It also serves duplicate routes under `/insta_backtester/api/...`, `/insta_backtester/v1/...`, and `/v1/...` in case the platform routes backend traffic under the same app prefix or strips the endpoint prefix before forwarding traffic to the container. Legacy local routes under `/api/...` and old `/vectorbt_api/v1/...` routes are kept for compatibility.

The Docker image listens on port `8000`.

## Deployment Tests

```bat
cd /d D:\Finflock\bitbucket_upload\insta_backtester_backend
python manage.py check
python manage.py runserver
```

For a local remote-MCP test, run the MCP server container and set:

```env
MCP_SERVER_URL=http://localhost:8001/mcp
```

Then check:

```text
GET http://localhost:8000/api/mcp/status/
```

Chat test:

```text
POST http://localhost:8000/api/chat/
```

```json
{
  "message": "Backtest AAPL using RSI. Buy below 30 and sell above 70. Run Monte Carlo for 60 days.",
  "openai_api_key": "USER_OPENAI_KEY",
  "finnhub_api_key": "USER_FINNHUB_KEY"
}
```

Portfolio optimization test:

```text
POST http://localhost:8000/api/portfolio/optimize/
```

```json
{
  "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL"],
  "lookback": "2y",
  "resolution": "D",
  "objective": "max_sharpe",
  "risk_free_rate": 0,
  "allow_short": false,
  "max_weight": 0.6,
  "num_frontier_portfolios": 3000,
  "finnhub_api_key": "USER_FINNHUB_KEY"
}
```
