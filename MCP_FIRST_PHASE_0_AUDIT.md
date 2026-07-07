# MCP-First Refactor Phase 0 Audit

Date: 2026-07-07
Branch: `mcp-first-refactor`

## Repository State

- Working directory: `D:\Finflock\VectorBT`
- Related read-only strategy repository: `D:\Finflock\stock_strategy_profilling`
- Starting branch: `TA-LIb-Addition-in-MCP-Server`
- Feature branch created: `mcp-first-refactor`
- Pre-existing untracked files:
  - `VECTORBT_MCP_FIRST_IMPLEMENTATION_PLAN.md`
  - `mcp/.dockerignore`
- `rg --files` reports a pre-existing permission warning under `.tmp/pytest/pytest-of-Lenovo/`.

## Current VectorBT Architecture

- MCP server is concentrated in `mcp/server.py`.
- Current MCP tools:
  - `list_strategies`
  - `get_strategy_schema`
  - `list_indicators`
  - `get_indicator_info`
  - `compute_indicator`
  - `compute_indicators_batch`
  - `list_stock_universe`
  - `list_sectors`
  - `list_stocks_by_sector`
  - `resolve_symbols_for_sector`
  - `fetch_market_data_summary`
  - `run_strategy_backtest`
  - `run_monte_carlo_simulation`
  - `run_strategy_research`
  - `run_markowitz_optimization`
  - `construct_factor_portfolio`
- Current Django backend is thin when `MCP_ENABLED=true`, but still contains local backtest fallback logic.
- Current frontend hardcodes strategy types, labels, defaults, and select options in `App.tsx`, `api/client.ts`, and `BacktestForm.tsx`.
- Analytics persistence currently uses raw PostgreSQL SQL in `docker/postgres/init-analytics.sql` plus direct `psycopg` writes in `backend/apps/analytics/services.py`.
- Metabase support is present through a separate Metabase database and `metabase_reader` grants on the analytics database.

## Current Profiling Repository Architecture

- `stock_strategy_profilling` contains a 275-strategy structured catalogue in `inputs/strategy_definitions.json`.
- Per-strategy JSON definitions are available under `outputs/strategy_json/definitions/`.
- Strategy logic is cross-sectional ranking based on `screening_rules` and `ranking_factors`.
- Readiness status is determined from available feature columns and ranking rules.
- Discovery searches OpenAlex, Crossref, and arXiv, then uses LLM extraction only for candidate structure.
- Duplicate checks, data availability checks, backtesting, classification, scoring, and promotion are deterministic Python code.

## Baseline Commands

- `python -m pytest` in `mcp`: passed, 59 tests.
- `python manage.py check` in `backend`: passed.
- `python manage.py test` in `backend`: passed, 29 tests.
- `npm run test:portfolio` in `frontend`: passed, 4 tests.
- `docker compose config`: passed.
- `PYTHONPATH=D:\Finflock\stock_strategy_profilling\src python -m pytest` in `stock_strategy_profilling`: passed, 18 tests.

## Baseline Failures and Warnings

- `npm run build` in `frontend` failed after TypeScript compilation and Vite transformation:
  - `EPERM: operation not permitted, unlink 'D:\Finflock\VectorBT\frontend\dist\assets\index-CYKQJ75N.css'`
  - This appears to be a pre-existing Windows filesystem/build artifact lock in `frontend/dist`.
- `stock_strategy_profilling` tests pass but emit existing pandas `PerformanceWarning` messages from highly fragmented DataFrame construction in `src/strategy_lab/strategies/features.py`.

## Important Pre-Refactor Findings

- `run_strategy_research` currently runs Monte Carlo on raw close prices after strategy backtests. The implementation plan requires strategy-workflow Monte Carlo to use strategy/equity returns.
- Current Markowitz optimization uses raw asset close returns. The new multi-stock research workflow must use strategy-conditioned return series when a strategy is selected.
- There are no Django model migrations for analytics persistence; existing persistence is SQL-first.
- There is no SSE streaming chat endpoint yet; chat is a synchronous POST.
- There is no installed/local A2UI dependency in `frontend/package.json`; A2UI integration needs package/API/license verification before implementation.
