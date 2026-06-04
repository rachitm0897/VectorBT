# VectorBT Strategy Lab Frontend

React + TypeScript + Vite + Tailwind frontend for the VectorBT Strategy Lab.

The app includes the existing strategy backtest/chat dashboard plus a Portfolio Optimizer panel for sector-wise Markowitz optimization using the backend-proxied US stock universe.

## Setup

```bash
npm install
copy .env.example .env
```

## Environment

- `VITE_API_BASE_URL`: backend base. Deployment uses `https://qfsplatform.com/insta_backtester`; local development defaults to `http://localhost:8000/api`.
- `VITE_MCP_STATUS_PATH`: MCP status path. Defaults to `/api/mcp/status/`.
- `VITE_APP_BASE_PATH`: optional frontend base path alias.
- `VITE_FRONTEND_BASE`: frontend base path. Defaults to `/insta_backtester_frontend/`.
- `VITE_BACKEND_PROXY_TARGET`: optional local backend proxy target for `/insta_backtester/api`.
- `VITE_DEV_PORT`: optional Vite dev port. Defaults to `5173`.

## API Keys Panel

The frontend asks for OpenAI and Finnhub keys in the sidebar. Keys stay in page memory for the current browser tab and are sent only to the Django backend as `X-OpenAI-API-Key` and `X-Finnhub-API-Key` request headers. Portfolio optimization sends the Finnhub key to the backend for MCP market data and does not add new key persistence.

## Portfolio Optimizer

The Portfolio Optimizer panel loads sectors and stocks from:

```text
GET /api/universe/sectors/
GET /api/universe/stocks/?sector=Technology
```

It submits selected symbols to:

```text
POST /api/portfolio/optimize/
```

Results show optimal weights, expected annual return, annual volatility, Sharpe ratio, an efficient frontier chart, a correlation heatmap, warnings, and the MCP artifact link when available. If universe endpoints are unavailable, the manual symbol input remains usable.

## Development

```bash
npm run dev
```

Default local URL:

```text
http://localhost:5173/insta_backtester_frontend/
```

Run the backend split repo on `http://localhost:8000`.

## Build

```bash
npm run build
```

## Docker

```bash
docker build -t vectorbt-frontend:local .
docker run --rm -p 127.0.0.1:8000:8000 vectorbt-frontend:local
```

The Docker image builds the Vite app and serves static files through nginx on port `8000`.

## QFS Platform

Use `/insta_backtester_frontend/` as the frontend path and `https://qfsplatform.com/insta_backtester` as the backend base. The deployment build calls:

```text
https://qfsplatform.com/insta_backtester/api/backtest/
https://qfsplatform.com/insta_backtester/api/chat/
https://qfsplatform.com/insta_backtester/api/portfolio/optimize/
https://qfsplatform.com/insta_backtester/api/universe/sectors/
https://qfsplatform.com/insta_backtester/api/universe/stocks/
https://qfsplatform.com/insta_backtester/api/mcp/status/
```

If QFS gives the backend a different route, build the frontend with `VITE_API_BASE_URL` set to that backend path.

## Deployment Tests

```bat
cd /d D:\Finflock\bitbucket_upload\insta_backtester_frontend
npm install
npm run build
```
