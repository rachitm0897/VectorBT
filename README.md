# Local Docker Setup with Metabase

This prototype runs the backend, frontend, MCP server, analytics PostgreSQL database, Metabase application database, and Metabase UI with one Docker Compose command.

## Start

```bash
docker compose up --build
```

## URLs

```text
Frontend: http://localhost:5173
Backend: http://localhost:8000
MCP: http://localhost:8001/mcp
Metabase: http://localhost:3000
```

## Metabase First Login

Open `http://localhost:3000` and create the first admin user.

## Connect Metabase to Analytics DB

```text
Database type: PostgreSQL
Host: analytics_db
Port: 5432
Database: analytics
User: metabase_reader
Password: metabase_reader_password
```

Inside Docker, the database host is `analytics_db`, not `localhost`.

## Persisted Data

- Backtest runs
- Strategy parameters
- Trades
- Equity points
- Markowitz portfolio optimization runs
- Portfolio weights
- MCP tool calls

## Not Stored

- OpenAI or chat API keys
- Finnhub API keys
- Raw secrets

User-provided Chat URL, Chat API key, model, and Finnhub API key still flow from the frontend to the backend request path. They are not stored in PostgreSQL or Metabase.

## Stop

```bash
docker compose down
```

## Reset Local Data

```bash
docker compose down -v
```

## Suggested Metabase Dashboards

- Backtest Overview
- Strategy Comparison
- Markowitz Portfolio Runs
- Portfolio Weights
- MCP Tool Calls
- Data Quality

## Full Research Data Seeding

Run the full real research seed through the existing backend -> MCP -> analytics persistence path:

```bash
docker compose exec backend python manage.py seed_full_research_data --finnhub-api-key "YOUR_FINNHUB_KEY"
```

The seed runs:

- 810 strategy backtests
- 96 Markowitz optimizations
- 906 total jobs

Selected 30 stocks:

```text
AAPL, MSFT, NVDA, GOOGL, META, AMZN, TSLA, AVGO, JPM, BAC, GS, V, MA, XOM, CVX, COP, JNJ, LLY, UNH, ABBV, MRK, HD, NKE, SBUX, MCD, WMT, AMD, CRM, CAT, BA
```

Optional flags:

```text
--force
--dry-run
--max-runs 100
--sleep 1.0
--skip-backtests
--skip-markowitz
--fail-on-error
```

The command prints per-job progress, skips successful existing analytics rows by deterministic run ID, continues after individual failures, and prints a final summary.

After seeding, open Metabase:

```text
http://localhost:3000
```

Useful validation SQL:

```sql
SELECT COUNT(*) FROM backtest_runs;
SELECT COUNT(*) FROM portfolio_optimization_runs;
SELECT COUNT(*) FROM portfolio_weights;
SELECT COUNT(*) FROM mcp_tool_calls;
```

## Example SQL

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

Markowitz runs:

```sql
SELECT
    created_at,
    objective,
    selection_mode,
    sector,
    symbols_used,
    expected_annual_return_pct,
    annual_volatility_pct,
    sharpe_ratio
FROM portfolio_optimization_runs
WHERE status = 'success'
ORDER BY created_at DESC;
```

Portfolio weights:

```sql
SELECT
    run_id,
    ticker,
    sector,
    weight
FROM portfolio_weights
ORDER BY run_id, weight DESC;
```

MCP tool calls:

```sql
SELECT
    DATE(created_at) AS date,
    tool_name,
    COUNT(*) AS calls,
    AVG(runtime_ms) AS avg_runtime_ms,
    COUNT(*) FILTER (WHERE status = 'error') AS errors
FROM mcp_tool_calls
GROUP BY DATE(created_at), tool_name
ORDER BY date DESC;
```

## Local Service Routing

```text
Backend calls MCP: http://mcp:8001/mcp
Frontend calls backend from browser: http://localhost:8000
Metabase connects to analytics DB: analytics_db:5432
Backend connects to analytics DB: analytics_db:5432
```
