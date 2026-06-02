# VectorBT Standalone Strategy Server

This is a standalone prototype MCP server for financial strategy research. It is independent from the existing Django and React application in this repository and does not import from that application.

The server fetches daily OHLCV candles from Finnhub, generates simple strategy signals, runs VectorBT backtests, performs bootstrap Monte Carlo forward simulations, and returns compact JSON responses suitable for LLM and MCP clients.

## Tools

- `list_strategies`: lists supported strategies.
- `get_strategy_schema`: returns parameter schema for one strategy.
- `fetch_market_data_summary`: fetches or loads cached OHLCV data and returns a compact summary.
- `run_strategy_backtest`: runs one strategy backtest and saves chart-ready artifacts.
- `run_monte_carlo_simulation`: runs bootstrap Monte Carlo simulation and saves paths as an artifact.
- `run_strategy_research`: high-level research workflow with backtest and optional Monte Carlo.

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
pip install -e .
```

For tests:

```bash
pip install -e ".[dev]"
```

## Environment

Create `.env` in this folder:

```bash
FINNHUB_API_KEY=your_key
```

Optional settings:

```bash
MCP_CACHE_DIR=standalone_mcp_server/cache
DEFAULT_INITIAL_CASH=10000
DEFAULT_FEES=0.001
```

## Run

```bash
python server.py
```

From the repository root, this also works:

```bash
python standalone_mcp_server/server.py
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
  "monte_carlo_simulations": 500
}
```

Company names are normalized for common names such as Apple, Tesla, Nvidia, Microsoft, Amazon, Meta, Facebook, Google, Alphabet, and Netflix.

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

Artifact JSON files may include OHLCV records, strategy signals, indicators, equity and drawdown curves, trades, Monte Carlo percentile paths, and sample paths. The compact MCP response includes `artifact_path`.

## Limitations

- Prototype only, not production-grade.
- Daily Finnhub candles only.
- Supported lookbacks: `1mo`, `6mo`, `1y`, `2y`, `5y`.
- Long-only signal backtests only.
- No broker APIs, live trading, authentication, Django, React, Celery, Redis, PostgreSQL, or TA-Lib.
- Backtest metrics depend on VectorBT availability and may be `null` if a metric cannot be extracted.
- Finnhub API limits and market data availability are external constraints.
