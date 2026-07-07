# VectorBT End-to-End Quant Research Platform
## MCP-First Implementation Plan

## 1. Objective

Turn `D:\Finflock\VectorBT\` into an end-to-end quantitative research platform powered by a clean, extensible MCP research engine.

The product must support:

1. Existing strategy search and selection from `D:\Finflock\stock_strategy_profilling\`.
2. Single-stock strategy backtesting.
3. Multi-stock strategy execution.
4. Strategy-conditioned Markowitz optimization.
5. Portfolio backtesting.
6. Monte Carlo simulation for both strategy and portfolio workflows.
7. LLM-powered strategy discovery.
8. Human review, validation, backtesting, classification and promotion of new strategies.
9. A2UI-based reusable frontend templates.
10. Persistent strategy, run, metric, allocation, trade, simulation, discovery and artifact storage in PostgreSQL.
11. Streaming AI chat responses.

The current MCP server should be refactored into a proper research engine, not left as one growing file full of tools. Because apparently even Python files deserve a spine.

---

## 2. Main Design Decision

Keep the quantitative logic inside MCP.

Django should remain thin.

React should remain a renderer and interaction layer.

```text
React + A2UI Frontend
        |
        | HTTP + SSE
        v
Django Backend
- auth
- users
- sessions
- chat history
- streaming proxy
- request validation
- MCP client
- database API
- permissions
        |
        v
MCP Quant Research Engine
- strategy registry
- strategy import
- strategy validation
- market data
- signal generation
- backtesting
- Markowitz optimization
- Monte Carlo
- discovery
- candidate processing
- result packaging
- artifact creation
        |
        v
PostgreSQL Analytics DB
```

The backend should not become the financial engine.

The frontend should not call MCP directly.

The LLM should not see dozens of low-level tools.

---

## 3. Core Refactor: MCP Server

The biggest implementation priority is to clean and restructure the MCP server.

### Current problem

The MCP server currently exposes useful tools, but the structure is too flat:

- tool definitions;
- request parsing;
- business logic;
- artifact handling;
- workflow logic;
- error handling;
- server routes

are too tightly coupled.

This is fine for a prototype. It is not fine for the product described here.

### Target structure

Refactor MCP into this structure:

```text
mcp/
  server.py
  app/
    bootstrap.py
    settings.py
    logging.py
    errors.py
    registry.py
  tools/
    public.py
    legacy.py
  workflows/
    single_stock.py
    multi_stock.py
    strategy_comparison.py
    discovery.py
    registry_search.py
  services/
    market_data.py
    strategy_registry.py
    strategy_importer.py
    strategy_validation.py
    signal_engine.py
    vectorbt_engine.py
    portfolio_optimizer.py
    monte_carlo_engine.py
    discovery_engine.py
    classification_engine.py
    persistence.py
    artifacts.py
    ui_spec_builder.py
  schemas/
    common.py
    strategies.py
    workflows.py
    results.py
    discovery.py
    ui.py
  repositories/
    strategy_repo.py
    run_repo.py
    artifact_repo.py
    discovery_repo.py
  adapters/
    stock_strategy_profilling.py
    finnhub.py
    openai_client.py
    research_sources.py
  tests/
```

Keep the exact structure flexible if the existing repository suggests a better layout, but the separation of responsibilities must be implemented.

---

## 4. MCP Tool Philosophy

Expose a small number of high-level public tools.

Do not expose every internal function to the LLM.

### Public MCP tools

Recommended public tools:

1. `search_strategy_registry`
2. `get_strategy_details`
3. `run_single_stock_research`
4. `run_multi_stock_research`
5. `compare_strategies`
6. `discover_strategy_candidates`
7. `review_strategy_candidate`
8. `process_approved_strategy`
9. `get_research_run`
10. `list_research_runs`
11. `get_artifact_summary`

### Legacy tools

Keep existing tools working where practical:

- `list_strategies`
- `get_strategy_schema`
- `list_stock_universe`
- `list_sectors`
- `list_stocks_by_sector`
- `resolve_symbols_for_sector`
- `fetch_market_data_summary`
- `run_strategy_backtest`
- `run_monte_carlo_simulation`
- `run_strategy_research`
- `run_markowitz_optimization`

But mark them internally as legacy wrappers around the new services.

The frontend and new backend chat workflows should use the new high-level tools.

### Why this matters

A large tool list hurts:

- latency;
- token usage;
- tool choice accuracy;
- maintainability;
- testing;
- future workflows.

The LLM should select workflows, not individual low-level calculation steps.

---

## 5. Internal MCP Service Boundaries

### 5.1 Strategy Registry Service

Responsibilities:

- load strategies from DB;
- import strategies from `stock_strategy_profilling`;
- normalize strategy schemas;
- search by metadata;
- filter by readiness;
- filter by execution type;
- provide parameter schemas;
- provide template hints;
- version strategy definitions;
- preserve source references.

### 5.2 Strategy Importer Service

Reads from:

`D:\Finflock\stock_strategy_profilling\`

Should import:

- catalogue JSON;
- per-strategy JSON;
- strategy scores;
- readiness status;
- risk-return metrics;
- classification metrics;
- source metadata;
- implementation details where available.

Import must be idempotent.

It should:

- preserve stable strategy IDs;
- compute content hash;
- upsert changed strategies;
- skip unchanged strategies;
- record import errors;
- never silently overwrite reviewed local edits.

### 5.3 Strategy Validation Service

Before execution, validate:

- strategy exists;
- strategy is executable;
- selected execution type is supported;
- required features exist;
- selected symbols have enough data;
- parameters match JSON Schema;
- long-short support is valid;
- required market data is available.

Unsupported strategies should remain searchable but non-runnable.

No fake results. The world already has enough fake alpha.

### 5.4 Market Data Service

Responsibilities:

- Finnhub daily and hourly data;
- caching;
- cache metadata;
- data quality checks;
- aligned multi-symbol data;
- missing-data reports;
- benchmark retrieval;
- optional future providers.

### 5.5 Signal Engine

Responsibilities:

- generate single-asset entry/exit signals;
- generate cross-sectional ranks;
- generate portfolio candidate selections;
- expose indicators used for charts;
- return aligned strategy returns;
- handle feature dependencies.

### 5.6 VectorBT Engine

Responsibilities:

- run single-stock backtests;
- run strategy-conditioned per-symbol backtests;
- run weighted portfolio backtests;
- extract equity, returns, trades, drawdowns and metrics;
- normalize metrics into shared result schema.

### 5.7 Portfolio Optimizer Service

Responsibilities:

- expected-return estimation;
- covariance estimation;
- covariance regularization;
- max Sharpe;
- min volatility;
- target return;
- target volatility;
- long-only constraints;
- bounded long-short constraints;
- gross exposure limits;
- net exposure constraints;
- efficient frontier generation;
- optimization warnings.

### 5.8 Monte Carlo Engine

Responsibilities:

- simulate from strategy returns;
- simulate from optimized portfolio returns;
- optionally simulate raw asset returns as a separate explicit mode;
- percentile paths;
- terminal distribution;
- loss probability;
- expected shortfall;
- drawdown distribution;
- deterministic seeds;
- simulation artifacts.

Important correction:

Monte Carlo after a strategy backtest should not normally use raw close-price returns. It should use strategy/equity returns.

Monte Carlo after portfolio optimization should use optimized portfolio returns.

### 5.9 Discovery Engine

Responsibilities:

- OpenAlex search;
- Crossref search;
- arXiv search;
- paper metadata capture;
- LLM extraction into strict schema;
- duplicate check;
- data availability check;
- implementability check;
- candidate persistence;
- review state transitions;
- approved strategy processing;
- promotion to registry.

### 5.10 Classification Engine

Responsibilities:

- horizon classification;
- risk-return scoring;
- robustness scoring;
- readiness assignment;
- confidence calculation;
- preserving raw metrics.

Use deterministic logic. Do not ask the LLM to classify final performance.

### 5.11 Persistence Service

Responsibilities:

- save strategy imports;
- save research runs;
- save backtests;
- save trades;
- save equity and drawdown series;
- save optimization runs;
- save weights;
- save Monte Carlo runs;
- save discovery candidates;
- save UI artifacts;
- provide IDs to the backend.

MCP should be able to persist results, but Django should still enforce user-facing permissions when reading them.

### 5.12 UI Spec Builder

Responsibilities:

- convert workflow results into safe A2UI template specs;
- select template ID;
- validate component props;
- downsample large series;
- attach artifact references;
- avoid arbitrary React or JavaScript generation.

---

## 6. Standard MCP Request and Result Schemas

Use strict Pydantic schemas for all public tools.

### Common request fields

- user/session context if supplied by backend;
- idempotency key;
- symbols;
- strategy ID;
- parameters;
- lookback;
- resolution;
- initial cash;
- fees;
- benchmark;
- Monte Carlo settings;
- optimization settings;
- output/detail level.

### Common result envelope

```text
status
workflow_type
run_id
strategy
strategy_version
universe
parameters
data_quality
summary
metrics
allocations
trades
equity
drawdown
monte_carlo
frontier
comparison
warnings
errors
artifacts
ui_hint
ui_spec
persistence
diagnostics
```

Large data should be persisted and referenced, not stuffed into prompts or oversized responses.

---

## 7. Canonical Strategy Registry

Create one strategy schema shared by:

- MCP;
- Django;
- React;
- imported profiling catalogue;
- A2UI templates;
- database persistence.

Each strategy should support:

- stable strategy ID;
- name;
- aliases;
- description;
- family;
- source type;
- source references;
- horizon bucket;
- required data;
- required features;
- parameter JSON Schema;
- default parameters;
- signal/ranking rules;
- execution type;
- long-only support;
- long-short support;
- readiness status;
- implementation version;
- classification metrics;
- risk score;
- return score;
- risk-adjusted score;
- robustness score;
- final score;
- template hint;
- active/deprecated status;
- source hash.

### Execution types

Support:

- `single_asset_signal`
- `cross_sectional_ranking`
- `portfolio_strategy`
- `research_only`

### Readiness states

Support:

- `BACKTEST_READY`
- `MISSING_DATA`
- `RULES_INCOMPLETE`
- `BACKTEST_FAILED`
- `RESEARCH_ONLY`
- `DEPRECATED`

All strategies should be searchable.

Only executable strategies should be runnable.

---

## 8. Product Panels

## 8.1 AI Research Chat

Streaming ChatGPT-style panel.

Capabilities:

- find existing strategies;
- explain strategies;
- backtest a stock;
- run multi-stock strategy workflows;
- optimize portfolios;
- allow bounded shorts;
- run Monte Carlo;
- compare strategies;
- discover new strategies;
- review results;
- retrieve past runs.

### Chat workflow

```text
User message
    ->
Django SSE endpoint
    ->
Intent router
    ->
LLM extracts structured parameters
    ->
Django calls high-level MCP tool
    ->
MCP streams/provides progress
    ->
Django streams updates to frontend
    ->
A2UI renders safe template
```

The LLM should not calculate finance metrics.

The LLM should not see the entire catalogue.

The LLM should not emit arbitrary React.

## 8.2 Manual Research Lab

Works without the LLM.

### Single stock

```text
Select stock
    ->
Select executable strategy
    ->
Load dynamic parameter schema
    ->
Run single-stock MCP workflow
    ->
Backtest
    ->
Strategy-return Monte Carlo
    ->
Persist
    ->
Render dashboard
```

### Multiple stocks

```text
Select stocks
    ->
Select one executable strategy
    ->
Run strategy on each stock
    ->
Build aligned strategy returns
    ->
Run Markowitz optimization
    ->
Backtest weighted portfolio
    ->
Portfolio-return Monte Carlo
    ->
Persist
    ->
Render dashboard
```

If the user selects more than one stock, the normal path should be strategy-conditioned Markowitz, not raw buy-and-hold Markowitz.

## 8.3 Strategy Discovery Lab

Capabilities:

- search research sources;
- extract candidate strategy;
- show candidate details;
- duplicate check;
- data availability check;
- human edit/review;
- approve/reject;
- process approved;
- backtest over universe;
- classify and score;
- promote successful strategy.

Human approval is mandatory before promotion.

---

## 9. Database Persistence

Persist strategy and research data in PostgreSQL.

Recommended tables/entities:

- `strategies`
- `strategy_versions`
- `strategy_parameters`
- `strategy_sources`
- `strategy_import_runs`
- `strategy_import_errors`
- `strategy_candidates`
- `candidate_reviews`
- `research_runs`
- `research_run_symbols`
- `backtest_runs`
- `backtest_metrics`
- `trades`
- `equity_points`
- `drawdown_points`
- `portfolio_optimization_runs`
- `portfolio_weights`
- `efficient_frontier_points`
- `monte_carlo_runs`
- `monte_carlo_percentile_points`
- `monte_carlo_terminal_bins`
- `chat_threads`
- `chat_messages`
- `mcp_tool_calls`
- `ui_artifacts`

Every research run should record:

- user if available;
- strategy ID;
- strategy version;
- symbols;
- parameters;
- data period;
- engine version;
- run status;
- warnings;
- errors;
- timestamps;
- artifact references.

Use transactions for completed workflow persistence.

Partial failures should be recorded as failed runs, not dropped.

---

## 10. Backend Responsibilities

Django remains thin but important.

Responsibilities:

- authentication;
- users;
- sessions;
- chat history;
- research run history;
- MCP client;
- SSE streaming;
- request validation;
- API key handling;
- permission checks;
- rate limiting;
- artifact access;
- database API for frontend;
- admin/sync actions;
- health checks.

Django should not calculate backtest results, covariance matrices, simulations or strategy classifications.

---

## 11. Frontend and A2UI

## 11.1 Visual Direction

Terminal-like, professional, compact.

Use:

- near-black backgrounds;
- charcoal panels;
- muted grey borders;
- white/grey typography;
- restrained green, amber and red for semantic states;
- sharp corners or very small radius;
- no gradients;
- no bright decorative colours;
- no glassmorphism;
- monospaced font for metrics, tables, logs, IDs and controls;
- readable sans-serif for long explanations if needed;
- thin separators;
- compact spacing;
- desktop-first layout;
- accessible contrast.

The result should feel like a quant research terminal, not a neon dashboard for people who think Sharpe ratio is a personality trait.

## 11.2 A2UI Rules

First verify the exact A2UI package, API, compatibility and license.

Do not invent interfaces.

Use A2UI through a constrained local template registry.

The LLM may select:

- template ID;
- section order;
- titles;
- validated props;
- explanation text.

The LLM may not emit arbitrary React, JavaScript or executable UI code.

## 11.3 Templates

Build templates for:

1. single-stock research;
2. optimized multi-stock portfolio;
3. strategy comparison;
4. strategy catalogue/details;
5. Monte Carlo deep dive;
6. discovery candidate review;
7. universe backtest/classification;
8. error/data-quality report.

## 11.4 Charts

Build reusable chart components:

- price with entries/exits;
- equity curve;
- benchmark comparison;
- drawdown;
- rolling return;
- rolling volatility;
- monthly returns heatmap;
- trade return distribution;
- efficient frontier;
- portfolio weights;
- net/gross exposure;
- correlation matrix;
- Monte Carlo fan chart;
- terminal-value histogram;
- risk metric cards;
- universe ranking table;
- parameter table;
- data-quality table;
- processing logs.

Reduce unnecessary chart-library overlap where safe.

---

## 12. Implementation Phases

## Phase 0: Full Audit

- Inspect both repositories.
- Run current backend, frontend and MCP tests.
- Run frontend build.
- Run Docker Compose if practical.
- Identify existing migrations and analytics tables.
- Identify all current MCP tools and their callers.
- Create a feature branch.
- Record current failures before making changes.

## Phase 1: MCP Refactor Foundation

- Create MCP app/service/schema/workflow structure.
- Move current logic into services.
- Keep server.py small.
- Add typed errors and response helpers.
- Keep old public tool names as wrappers where practical.
- Add new high-level public tools.
- Add tests for existing tool compatibility.

## Phase 2: Strategy Registry and Import

- Add canonical strategy schema.
- Add database models/migrations if missing.
- Add importer from `stock_strategy_profilling`.
- Add idempotent sync command.
- Add strategy search/detail tools.
- Add readiness filtering.
- Persist strategy data and versions.

## Phase 3: Single-Stock Workflow

- Add high-level `run_single_stock_research`.
- Validate strategy and parameters.
- Run VectorBT backtest.
- Run Monte Carlo from strategy/equity returns.
- Persist complete workflow.
- Return standard result envelope and UI spec.

## Phase 4: Multi-Stock Workflow

- Add high-level `run_multi_stock_research`.
- Run selected strategy across each stock.
- Build aligned strategy return matrix.
- Run constrained Markowitz.
- Backtest weighted portfolio.
- Run Monte Carlo from portfolio returns.
- Persist weights, frontier, metrics and simulations.
- Return standard result envelope and UI spec.

## Phase 5: Backend Streaming and APIs

- Add MCP client improvements.
- Add SSE chat endpoint.
- Add deterministic intent router.
- Add structured LLM extraction.
- Add research run APIs.
- Add artifact APIs.
- Add strategy registry APIs.
- Persist chat threads/messages.

## Phase 6: Frontend Revamp

- Build three-panel layout.
- Apply terminal design system.
- Replace hardcoded strategies with dynamic registry data.
- Add manual single/multi-stock lab.
- Add streaming chat UI.
- Add A2UI template renderer.
- Add chart components.
- Add run history and artifact views.

## Phase 7: Discovery Lab

- Integrate discovery workflow from profiling repo.
- Add candidate search, extraction and storage.
- Add review/edit/approve/reject UI.
- Add process-approved workflow.
- Add universe backtest/classification display.
- Promote successful candidates into registry.

## Phase 8: Reliability

- Add idempotency keys.
- Add caching.
- Add retries/timeouts.
- Add cancellation where practical.
- Add background execution for long workflows if needed.
- Add downsampling for large charts.
- Add telemetry.
- Add tests.
- Validate Docker Compose.

---

## 13. Acceptance Criteria

The implementation is complete when:

1. Existing VectorBT functionality still works.
2. MCP server code is modular, typed and testable.
3. High-level MCP tools exist and are used by new workflows.
4. Legacy MCP tools still work where practical.
5. Strategies from `stock_strategy_profilling` are imported and persisted.
6. Strategy readiness is respected.
7. The frontend no longer hardcodes strategy options.
8. One-stock workflow runs backtest and strategy-return Monte Carlo.
9. Multi-stock workflow runs strategy-conditioned Markowitz, portfolio backtest and portfolio Monte Carlo.
10. Long-short optimization is bounded and validated.
11. AI chat streams responses.
12. AI chat can find and run existing strategies.
13. Discovery lab can search, review, process and promote strategies.
14. A2UI renders only safe local templates.
15. Results, metrics, trades, weights, simulations and artifacts are persisted.
16. Docker Compose starts the complete system.
17. Tests cover registry import, workflows, persistence, streaming and discovery.

---

## 14. Important Constraints

- Work primarily inside `D:\Finflock\VectorBT\`.
- Read `D:\Finflock\stock_strategy_profilling\`.
- Do not blindly merge both repositories.
- Do not rewrite everything from scratch.
- Keep MCP as the quantitative engine.
- Keep Django thin.
- Keep React as renderer and interaction layer.
- Preserve Metabase support.
- Use migrations and typed schemas.
- Never invent unsupported strategy performance.
- Do not expose a huge low-level MCP tool list to the LLM.
