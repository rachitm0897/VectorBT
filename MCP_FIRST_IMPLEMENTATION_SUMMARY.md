# MCP-First Implementation Summary

Branch: `mcp-first-refactor`

## Architecture

- MCP is now the quantitative research engine.
- Django exposes thin REST/SSE endpoints and delegates strategy registry, research workflows, discovery and persistence to MCP tools.
- React loads registry data through Django APIs and renders interaction/results, including constrained A2UI template specs.
- `stock_strategy_profilling` is read by adapter/importer code only; no changes were made to that repository during implementation.

## MCP Refactor

`mcp/server.py` was reduced to bootstrap, health/artifact routes and tool registration.

New internal packages:

- `mcp/app`: settings, errors, logging, bootstrap and registry helpers.
- `mcp/schemas`: canonical strategy, workflow, result, discovery and UI schemas.
- `mcp/services`: market data, registry/import, validation, signal generation, vectorbt execution, optimizer, Monte Carlo, discovery, artifacts, persistence and UI spec builder.
- `mcp/workflows`: single-stock, multi-stock, strategy comparison, registry search and discovery orchestration.
- `mcp/repositories`: analytics database persistence helpers.
- `mcp/adapters`: `stock_strategy_profilling` catalogue adapter.
- `mcp/tools/public.py`: high-level MCP tools.
- `mcp/tools/legacy.py`: compatibility wrappers for previous tools.

Public high-level tools:

- `search_strategy_registry`
- `get_strategy_details`
- `run_single_stock_research`
- `run_multi_stock_research`
- `compare_strategies`
- `discover_strategy_candidates`
- `review_strategy_candidate`
- `process_approved_strategy`
- `get_research_run`
- `list_research_runs`
- `get_artifact_summary`
- `sync_strategy_registry`

Legacy tools retained:

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

## Strategy Registry

- Built-in executable strategies are normalized to the canonical strategy schema.
- `stock_strategy_profilling` catalogue JSON files are imported via adapter logic, with stable IDs, source references, canonical execution/readiness fields and SHA-256 source hashes.
- Import failures are returned explicitly.
- Imported cross-sectional/research strategies are searchable and viewable; only executable single-asset signal strategies are selectable for the current single/multi workflow backtests.

## Research Workflows

- Single-stock workflow validates symbol, strategy readiness, execution type and parameters, then fetches market data, generates signals, runs vectorbt, computes strategy returns, runs Monte Carlo from strategy returns, persists results and returns a standard envelope plus UI spec.
- Multi-stock workflow runs the selected strategy per symbol, aligns strategy return series, optimizes on strategy-conditioned returns, backtests the weighted strategy portfolio and runs Monte Carlo from portfolio returns.
- Monte Carlo engine supports explicit strategy, portfolio and raw-asset return modes. Workflow paths use strategy/portfolio returns, not raw close returns.

## Database

`docker/postgres/init-analytics.sql` adds analytics tables for:

- strategy registry/version/source/import data;
- candidate review data;
- research runs, symbols, metrics, trades, equity/drawdown, optimization/frontier and Monte Carlo outputs;
- chat threads/messages, MCP tool calls and UI artifacts.

Existing analytics/Metabase support and grants are preserved.

## Django Backend

Added thin endpoints:

- `GET /api/strategies/`
- `GET /api/strategies/<strategy_id>/`
- `POST /api/research/single/`
- `POST /api/research/multi/`
- `GET /api/research/runs/`
- `GET /api/research/runs/<run_id>/`
- `POST /api/discovery/candidates/`
- `POST /api/discovery/candidates/<candidate_id>/review/`
- `POST /api/discovery/candidates/<candidate_id>/process/`
- `POST /api/chat/stream/`

Added management command:

- `python manage.py sync_strategy_registry`

The command delegates to MCP `sync_strategy_registry`.

## Frontend

- App shell is now an MCP-first research platform.
- Strategy options are loaded from backend registry APIs.
- First-class panels:
  - AI Research Chat with SSE event log;
  - Manual Research Lab for single and multi-stock strategy research;
  - Strategy Discovery Lab.
- Existing raw Markowitz and factor portfolio panels remain as collapsed compatibility tools.
- A2UI was verified and integrated through a constrained local template renderer.

## A2UI Verification

- Relevant package: `@a2ui/react` `0.10.1`, Apache-2.0.
- Core package: `@a2ui/web_core` `0.10.3`, Apache-2.0.
- React renderer uses v0.9 imports:
  - `A2uiSurface`, `basicCatalog` from `@a2ui/react/v0_9`;
  - `MessageProcessor` from `@a2ui/web_core/v0_9`.
- Installed React/React DOM were moved to `19.2.7` to satisfy A2UI peer requirements.
- Package warning: `@a2ui/markdown-it` declares a peer on `@a2ui/web_core ^0.9.2` while `@a2ui/react` uses `^0.10.1`.
- The documented CSS subpath did not resolve in the published package; the frontend uses the exported `injectStyles()` function instead.

## Tests

Passing:

- `cd mcp; python -m pytest` -> 65 passed.
- `cd backend; python manage.py check` -> no issues.
- `cd backend; python manage.py test` -> 29 passed.
- `cd frontend; npx tsc --noEmit -p tsconfig.json` -> passed.
- `cd frontend; npm run test:portfolio` -> 4 passed.
- `docker compose config` -> passed.
- `cd frontend; npx vite build --outDir dist-mcp-build` -> passed.

Known build environment issue:

- `cd frontend; npm run build` still fails while Vite tries to delete stale baseline file `frontend/dist/assets/index-CYKQJ75N.css`.
- Direct `Remove-Item` also fails with Windows access denied.
- This exact `EPERM` unlink failure existed in the baseline audit.

## Required API Keys / Accounts

- Finnhub API key for market data workflows.
- OpenAI-compatible chat API key for natural-language parsing and discovery extraction where the profiling pipeline requires it.
- Optional LangSmith credentials for tracing.
- PostgreSQL/Metabase are provided by Docker Compose for local analytics.

## Known Limitations

- Approved candidate processing currently returns an explicit `approved_processing_not_configured` error rather than fabricating strategy promotion/backtest results.
- Multi-stock strategy-conditioned optimization currently supports executable single-asset signal strategies; imported cross-sectional ranking strategies are searchable but not yet executed as portfolio strategies.
- PostgreSQL persistence is implemented as optional MCP-side analytics persistence and degrades to disabled/error metadata when analytics DB is unavailable.
- The SSE chat endpoint streams staged events around the current deterministic chat graph; deeper incremental MCP progress events can be added as workflow internals expose progress callbacks.
