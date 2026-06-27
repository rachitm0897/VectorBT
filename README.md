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
- Compact portfolio scenario summaries
- Factor portfolio runs
- Stock factor scores
- MCP tool calls

## Not Stored

- OpenAI or chat API keys
- Finnhub API keys
- Raw secrets

User-provided Chat URL, Chat API key, model, and Finnhub API key still flow from the frontend to the backend request path. They are not stored in PostgreSQL or Metabase.

## Portfolio Scenario Monte Carlo

The existing `run_markowitz_optimization` MCP tool can optionally run portfolio-level Monte Carlo scenario analysis after Markowitz weights are calculated. It uses the selected objective portfolio weights, builds historical weighted portfolio returns from the aligned close-price frame, and runs block-bootstrap simulations against the same optimized portfolio.

Available presets:

- `neutral`: drift shift `0.00`, volatility multiplier `1.00`, initial shock `0.00`
- `bullish`: drift shift `0.08`, volatility multiplier `0.85`, initial shock `0.00`
- `bearish`: drift shift `-0.08`, volatility multiplier `1.25`, initial shock `0.00`
- `crash`: drift shift `-0.10`, volatility multiplier `1.75`, initial shock `-0.15`

These values are configurable assumptions for scenario testing, not market forecasts.

Example request:

```json
{
  "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL"],
  "objective": "max_sharpe",
  "lookback": "2y",
  "resolution": "D",
  "monte_carlo": {
    "enabled": true,
    "days": 60,
    "simulations": 500,
    "block_size": 5,
    "seed": 42,
    "scenarios": ["neutral", "bullish", "bearish", "crash"],
    "scenario_overrides": {}
  }
}
```

Natural language example:

```text
Create a max Sharpe portfolio from Technology stocks and test neutral, bullish, bearish and crash scenarios for 60 days.
```

Compact results are returned under `portfolio_result.scenario_analysis` with the actual assumptions and summary metrics used for each scenario. Full percentile paths and up to 20 sample paths per scenario are stored in the MCP artifact under `scenario_analysis.scenarios`. PostgreSQL persistence stores only compact scenario summaries inside the existing redacted JSON fields, not full simulation paths.

## Factor Portfolio Construction

The MCP server also exposes `construct_factor_portfolio`, a factor-ranked stock selection workflow that feeds the existing Markowitz optimizer and portfolio scenario Monte Carlo engine.

```text
Stock Universe
-> Fetch price and fundamental data
-> Calculate factor scores
-> Rank and filter stocks
-> Run Markowitz optimisation
-> Run portfolio Monte Carlo scenarios
-> Display and persist results
```

These are internally calculated research scores inspired by common fundamental and quantitative investment methods. They are not official Morningstar or StarMine ratings and should not be presented as such.

Score groups:

- Fundamental Quality Score: profitability, growth, cash generation, leverage, liquidity, interest coverage, and earnings consistency. Higher profitability, growth, cash generation, and consistency improve the score. Higher leverage reduces it.
- Valuation Score: price-to-earnings, forward P/E when available, price-to-book, price-to-sales, enterprise-value-to-EBITDA, and free-cash-flow yield. Lower valid multiples generally rank better; higher free-cash-flow yield ranks better.
- Momentum Score: 1-month, 3-month, 6-month, and 12-month returns, return excluding the latest month, distance from 50-day and 200-day moving averages, and relative strength against the evaluated universe.
- Analyst and Earnings Score: recommendation mix, estimate/revision fields, target-price upside, earnings surprises, and expected earnings changes when provider data is available.
- Financial Risk Score: historical volatility, maximum drawdown, downside volatility, beta when available, leverage, earnings variability, and a simple distress proxy. Higher score means lower measured risk.

Each raw factor is winsorised, ranked within the selected universe or sector, converted to a 0-100 score, and reversed when lower raw values are better. Missing values do not receive an automatic zero or perfect score. Available score groups are reweighted proportionally and `data_coverage_pct` is returned for every stock.

Default factor weights:

```text
Fundamental quality: 30%
Valuation: 20%
Momentum: 20%
Analyst and earnings signals: 15%
Financial risk: 15%
```

Selection methods:

- `top_n`
- `top_percentile`
- `minimum_score`
- `all_eligible`

Expected-return methods:

- `historical`: use historical annualized returns in Markowitz optimization.
- `factor_tilted`: start from historical returns, adjust by centred combined score, apply tilt strength, and cap the annual adjustment. These adjusted returns are assumptions, not forecasts.

Example MCP request:

```json
{
  "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
  "sector": null,
  "selection_mode": "symbols",
  "lookback": "2y",
  "resolution": "D",
  "factor_model": {
    "enabled": true,
    "normalization_mode": "sector",
    "weights": {
      "fundamental_quality": 0.3,
      "valuation": 0.2,
      "momentum": 0.2,
      "analyst": 0.15,
      "financial_risk": 0.15
    },
    "minimum_data_coverage_pct": 60,
    "selection_method": "top_n",
    "top_n": 3,
    "minimum_score": null
  },
  "optimization": {
    "objective": "max_sharpe",
    "minimum_weight": 0,
    "maximum_weight": 0.25,
    "risk_free_rate": 0.04,
    "expected_return_method": "factor_tilted"
  },
  "score_tilt": {
    "enabled": true,
    "strength": 0.2,
    "maximum_adjustment_pct": 0.05
  },
  "monte_carlo": {
    "enabled": true,
    "days": 60,
    "simulations": 500,
    "block_size": 5,
    "seed": 42,
    "scenarios": ["neutral", "bullish", "bearish", "crash"]
  }
}
```

Natural-language examples:

```text
Create a factor-ranked maximum Sharpe portfolio from technology stocks.
Rank AAPL, MSFT, NVDA, GOOGL and META using quality, value and momentum, select the top three and run crash scenarios.
Build a low-risk portfolio using stocks with a combined score above 65.
```

Compact responses include `request_summary`, `universe_summary`, `factor_model_configuration`, compact `factor_scores`, `selected_stocks`, `rejected_stocks`, `optimization_result`, `portfolio_weights`, compact `scenario_analysis`, warnings, data sources, and an artifact link. Detailed raw factor values, normalized factor scores, effective weights, selected/rejected records, Markowitz artifacts, and scenario chart paths are stored in the MCP artifact when available.

### Factor Analytics Tables

`factor_portfolio_runs` stores one row per factor construction run:

```text
run_id, created_at, status, selection_mode, sector, symbols_requested,
symbols_scored, symbols_selected, factor_configuration, normalization_mode,
selection_method, top_n, minimum_score, minimum_data_coverage_pct,
optimization_objective, expected_return_method, expected_annual_return_pct,
annual_volatility_pct, sharpe_ratio, scenario_summary, warnings, runtime_ms
```

`stock_factor_scores` stores one row per scored stock:

```text
run_id, ticker, company_name, sector, fundamental_quality_score,
valuation_score, momentum_score, analyst_score, financial_risk_score,
quantitative_alpha_score, combined_portfolio_score, data_coverage_pct,
selection_status, selection_reason, expected_return_original,
expected_return_adjusted, final_portfolio_weight, raw_values_json,
normalized_scores_json, effective_weights_json
```

Full Monte Carlo simulation paths are not stored in PostgreSQL. Only compact scenario summaries are persisted.

Example Metabase SQL:

```sql
SELECT created_at, sector, symbols_scored, symbols_selected,
       expected_annual_return_pct, annual_volatility_pct, sharpe_ratio
FROM factor_portfolio_runs
ORDER BY created_at DESC;
```

```sql
SELECT ticker, sector, combined_portfolio_score, data_coverage_pct,
       selection_status, final_portfolio_weight
FROM stock_factor_scores
WHERE run_id = {{run_id}}
ORDER BY combined_portfolio_score DESC;
```

Limitations:

- Factor coverage depends on available Finnhub fields and cache freshness.
- Analyst and estimate data can be sparse; missing groups are reweighted rather than invented.
- Sector mode falls back to universe-style comparisons when too few sector peers are available.
- Sector scoring is capped in the prototype to limit provider calls.
- Factor-tilted expected returns are assumptions for scenario testing, not forecasts.

## LangSmith tracing

LangSmith tracing shows the top-level chat request, LangGraph nodes, direct OpenAI parser calls, selected MCP tools, sanitized tool inputs, compact output summaries, errors, token usage, and latency. With the default `streamable_http` transport, trace headers are propagated from the backend to the MCP server so one request appears as a nested trace tree.

Create a LangSmith API key, then set:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=finance-mcp-dev
```

Start the services and open the `finance-mcp-dev` project in LangSmith. Tracing remains disabled when `LANGSMITH_TRACING` is false or the API key is empty.

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

Docker Compose reads the same variables from the repository `.env`:

```bash
docker compose up --build
```

API keys, bearer tokens, passwords, and credential-shaped fields are redacted before custom inputs or metadata are sent. Large dataframes, candle arrays, indicator series, and artifacts are represented by compact summaries.

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
