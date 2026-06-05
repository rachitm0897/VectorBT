# VectorBT Standalone Strategy Server

This is a standalone prototype MCP server for financial strategy research. It is independent from the existing Django and React application in this repository and does not import from that application.

The server fetches daily OHLCV candles from Finnhub, computes indicators through TA-Lib, generates strategy signals, runs VectorBT backtests, performs bootstrap Monte Carlo forward simulations, runs prototype Markowitz portfolio optimization, and returns compact JSON responses suitable for LLM and MCP clients.

TA-Lib is used behind a small finance-oriented adapter. Individual TA-Lib functions are not exposed as separate MCP tools.

Supported strategies are `sma_crossover`, `rsi_mean_reversion`, `bollinger_reversion`, and `macd_crossover`. The MACD strategy enters when MACD crosses above its signal line and exits when it crosses below.

## Tools

- `list_strategies`: lists supported strategies.
- `get_strategy_schema`: returns parameter schema for one strategy.
- `list_indicators`: lists indicators available from TA-Lib.
- `get_indicator_info`: returns TA-Lib metadata for one indicator.
- `compute_indicator`: fetches one symbol and computes one indicator.
- `compute_indicators_batch`: fetches one symbol once and computes multiple indicators.
- `fetch_market_data_summary`: fetches or loads cached OHLCV data and returns a compact summary.
- `run_strategy_backtest`: runs one strategy backtest and saves chart-ready artifacts.
- `run_monte_carlo_simulation`: runs bootstrap Monte Carlo simulation and saves paths as an artifact.
- `run_strategy_research`: high-level research workflow with backtest and optional Monte Carlo.
- `list_sectors`: lists sectors from `us_stocks_only_universe.json`.
- `list_stocks_by_sector`: lists compact stock metadata for one sector.
- `list_stock_universe`: lists compact stock metadata, optionally filtered by sector.
- `run_markowitz_optimization`: optimizes selected universe stocks with max Sharpe or minimum volatility objectives and saves chart-ready frontier/correlation artifacts.

## Install

```bash
cd standalone_mcp_server
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Mac/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
conda install -c conda-forge ta-lib
pip install -e .
```

Verify TA-Lib:

```bash
python -c "import talib; print(talib.__version__)"
```

Recent Python and platform combinations may install TA-Lib from a binary wheel through `pip install -e .`. The conda command remains the recommended local fallback when a native TA-Lib library is not already available.

For tests:

```bash
pip install -e ".[dev]"
```

## Environment

Create `.env` in this folder:

```bash
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8001
MCP_TRANSPORT=streamable_http
MCP_BASE_PATH=/mcp
MCP_PUBLIC_BASE_URL=https://qfsplatform.com/insta_backtest_MCP_server
MCP_CACHE_DIR=/app/cache
FINNHUB_API_KEY=
```

`FINNHUB_API_KEY` is only an optional fallback. In the deployed app, the backend passes the user-provided Finnhub key in MCP tool arguments.

Optional defaults:

```bash
DEFAULT_INITIAL_CASH=10000
DEFAULT_FEES=0.001
```

The stock universe loader searches for the real `us_stocks_only_universe.json` at the repository root first. It does not create fallback universe data.
For Docker/QFS deployment, `insta_mcpserver/us_stocks_only_universe.json` is included in the MCP image and `MCP_US_STOCK_UNIVERSE_PATH` defaults to `/app/us_stocks_only_universe.json`.

## LangSmith tracing

All registered MCP tools are traced with `run_type="tool"` when LangSmith is enabled. Traces contain sanitized inputs, compact output or error summaries, request IDs, and per-tool latency. Large OHLCV, dataframe, indicator, portfolio, and artifact payloads are summarized instead of uploaded in full.

Set:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=finance-mcp-dev
```

Windows Miniforge or Command Prompt:

```bat
set LANGSMITH_TRACING=true
set LANGSMITH_API_KEY=your_key_here
set LANGSMITH_PROJECT=finance-mcp-dev
```

PowerShell:

```powershell
$env:LANGSMITH_TRACING="true"
$env:LANGSMITH_API_KEY="your_key_here"
$env:LANGSMITH_PROJECT="finance-mcp-dev"
```

Docker:

```bash
docker run --env-file .env -p 8001:8000 insta-mcpserver
```

The Django/LangGraph backend traces the user request and direct LLM call. For `streamable_http` and SSE transports it forwards LangSmith trace headers to this server, producing one nested request, LLM, MCP client, HTTP, and server tool tree. Stdio tool spans are still recorded, but dynamic parent trace headers cannot be propagated through the stdio transport.

Tracing is optional. Missing variables, a disabled flag, or a LangSmith export failure does not stop MCP tool execution.

## Run

Local stdio mode:

```bash
set MCP_TRANSPORT=stdio
python server.py
```

Remote HTTP mode:

```bash
set MCP_TRANSPORT=streamable_http
set MCP_SERVER_HOST=0.0.0.0
set MCP_SERVER_PORT=8001
set MCP_BASE_PATH=/mcp
python server.py
```

## Example MCP Config

```json
{
  "mcpServers": {
    "vectorbt-standalone-strategy-server": {
      "command": "python",
      "args": [
        "ABSOLUTE_PATH_TO_PROJECT/standalone_mcp_server/server.py"
      ],
      "env": {
        "FINNHUB_API_KEY": "your_finnhub_key"
      }
    }
  }
}
```

## Example Calls

List strategies:

```json
{}
```

Get a strategy schema:

```json
{
  "strategy": "sma_crossover"
}
```

Compute one indicator:

```json
{
  "symbol": "AAPL",
  "indicator": "RSI",
  "parameters": {
    "timeperiod": 14
  },
  "lookback": "2y",
  "resolution": "D",
  "finnhub_api_key": "USER_FINNHUB_KEY"
}
```

Compute an indicator batch with one Finnhub fetch:

```json
{
  "symbol": "AAPL",
  "indicators": [
    {
      "name": "SMA",
      "parameters": {
        "timeperiod": 20
      },
      "alias": "fast_sma"
    },
    {
      "name": "BBANDS",
      "parameters": {
        "timeperiod": 20,
        "nbdevup": 2,
        "nbdevdn": 2
      }
    }
  ],
  "lookback": "2y",
  "resolution": "D",
  "finnhub_api_key": "USER_FINNHUB_KEY"
}
```

Run research:

```json
{
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
  "run_monte_carlo": true,
  "monte_carlo_days": 60,
  "monte_carlo_simulations": 500,
  "finnhub_api_key": "USER_FINNHUB_KEY"
}
```

Company names are normalized for common names such as Apple, Tesla, Nvidia, Microsoft, Amazon, Meta, Facebook, Google, Alphabet, and Netflix.

Run Markowitz optimization:

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

The Finnhub key is used only for market data calls and is not stored in Markowitz artifacts.

## Artifact Storage

MCP responses are compact by default. They do not return full OHLCV arrays, equity curves, indicators, trades, or Monte Carlo paths.

Larger chart-ready data is saved under:

```text
standalone_mcp_server/cache/results/
```

Market data responses are cached under:

```text
standalone_mcp_server/cache/market_data/
```

Artifact JSON files may include OHLCV records, strategy signals, indicators, equity and drawdown curves, trades, Monte Carlo percentile paths, sample paths, Markowitz efficient frontier points, correlation matrices, and portfolio summaries. The compact MCP response includes `artifact_path`, `artifact_id`, and, when `MCP_PUBLIC_BASE_URL` is set, `artifact_url`.

In remote mode artifacts are served at:

```text
https://qfsplatform.com/insta_backtest_MCP_server/artifacts/{artifact_id}
```

## Docker Deployment

```bat
cd /d D:\Finflock\bitbucket_upload\insta_mcpserver
docker build -t insta-mcpserver .
docker run --env-file .env -p 8001:8001 insta-mcpserver
```

Then test:

```text
http://localhost:8001/health
http://localhost:8001/mcp
```

For qfsplatform deployment, the Docker image listens on port `8000` by default because the platform router expects the app container on that port. The local `.env` keeps `MCP_SERVER_PORT=8001` for manual local runs. If you run the Docker image without `--env-file .env`, use:

```bat
docker run -p 8001:8000 insta-mcpserver
```

Reverse proxy mapping:

```text
external: https://qfsplatform.com/insta_backtest_MCP_server/mcp
internal: http://mcp-container:8000/mcp
```

Artifact mapping:

```text
external: https://qfsplatform.com/insta_backtest_MCP_server/artifacts/{artifact_id}
internal: http://mcp-container:8000/artifacts/{artifact_id}
```

## Limitations

- Prototype only, not production-grade.
- Daily Finnhub candles only.
- Supported lookbacks: `1mo`, `6mo`, `1y`, `2y`, `5y`.
- Long-only signal backtests only.
- Indicator computation accepts standard OHLCV inputs; TA-Lib functions requiring additional input arrays may return a clear computation error.
- Markowitz optimization is prototype-grade and supports up to 20 selected universe stocks.
- No broker APIs, live trading, authentication, Django, React, Celery, Redis, or PostgreSQL.
- Backtest metrics depend on VectorBT availability and may be `null` if a metric cannot be extracted.
- Finnhub API limits and market data availability are external constraints.
