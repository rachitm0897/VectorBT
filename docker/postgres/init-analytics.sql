DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'metabase_reader') THEN
        CREATE USER metabase_reader WITH PASSWORD 'metabase_reader_password';
    ELSE
        ALTER USER metabase_reader WITH PASSWORD 'metabase_reader_password';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS backtest_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    source VARCHAR(64),
    status VARCHAR(32),
    error_message TEXT,

    request_type VARCHAR(64),
    symbol VARCHAR(32),
    strategy VARCHAR(128),
    lookback VARCHAR(32),
    resolution VARCHAR(16),

    initial_cash NUMERIC,
    fees NUMERIC,

    total_return_pct NUMERIC,
    buy_hold_return_pct NUMERIC,
    alpha_vs_buy_hold_pct NUMERIC,
    sharpe_ratio NUMERIC,
    max_drawdown_pct NUMERIC,
    win_rate_pct NUMERIC,
    total_trades INTEGER,
    final_value NUMERIC,

    monte_carlo_days INTEGER,
    monte_carlo_simulations INTEGER,
    mc_expected_return_pct NUMERIC,
    mc_probability_positive_pct NUMERIC,
    mc_p5_return_pct NUMERIC,
    mc_p95_return_pct NUMERIC,

    mcp_tool VARCHAR(128),
    mcp_transport VARCHAR(64),
    mcp_server_url TEXT,

    cache_status VARCHAR(32),
    candles_fetched INTEGER,

    request_json JSONB,
    metrics_json JSONB,
    summary_json JSONB,
    diagnostics_json JSONB
);

CREATE TABLE IF NOT EXISTS backtest_parameters (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL,
    parameter_name VARCHAR(128),
    parameter_value VARCHAR(256)
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL,
    symbol VARCHAR(32),
    strategy VARCHAR(128),
    entry_time TIMESTAMP NULL,
    exit_time TIMESTAMP NULL,
    side VARCHAR(32),
    entry_price NUMERIC,
    exit_price NUMERIC,
    pnl NUMERIC,
    return_pct NUMERIC,
    duration_days INTEGER,
    status VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS equity_points (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL,
    time TIMESTAMP,
    strategy_equity NUMERIC,
    buy_hold_equity NUMERIC,
    spy_equity NUMERIC,
    drawdown_pct NUMERIC
);

CREATE TABLE IF NOT EXISTS portfolio_optimization_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    status VARCHAR(32),
    error_message TEXT,

    objective VARCHAR(64),
    selection_mode VARCHAR(64),
    sector VARCHAR(128),

    symbols_requested INTEGER,
    symbols_used INTEGER,
    lookback VARCHAR(32),
    resolution VARCHAR(16),

    risk_free_rate NUMERIC,
    allow_short BOOLEAN,
    max_weight NUMERIC,
    num_frontier_portfolios INTEGER,

    expected_annual_return_pct NUMERIC,
    annual_volatility_pct NUMERIC,
    sharpe_ratio NUMERIC,

    min_vol_return_pct NUMERIC,
    min_vol_volatility_pct NUMERIC,
    min_vol_sharpe_ratio NUMERIC,

    max_sharpe_return_pct NUMERIC,
    max_sharpe_volatility_pct NUMERIC,
    max_sharpe_ratio NUMERIC,

    artifact_url TEXT,
    mcp_tool VARCHAR(128),
    mcp_transport VARCHAR(64),
    mcp_server_url TEXT,

    request_json JSONB,
    result_json JSONB,
    diagnostics_json JSONB
);

CREATE TABLE IF NOT EXISTS portfolio_weights (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL,
    ticker VARCHAR(32),
    company_name TEXT,
    sector VARCHAR(128),
    weight NUMERIC
);

CREATE TABLE IF NOT EXISTS factor_portfolio_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    status VARCHAR(32),
    selection_mode VARCHAR(64),
    sector VARCHAR(128),
    symbols_requested INTEGER,
    symbols_scored INTEGER,
    symbols_selected INTEGER,

    factor_configuration JSONB,
    normalization_mode VARCHAR(64),
    selection_method VARCHAR(64),
    top_n INTEGER,
    minimum_score NUMERIC,
    minimum_data_coverage_pct NUMERIC,

    optimization_objective VARCHAR(64),
    expected_return_method VARCHAR(64),
    expected_annual_return_pct NUMERIC,
    annual_volatility_pct NUMERIC,
    sharpe_ratio NUMERIC,

    scenario_summary JSONB,
    warnings JSONB,
    runtime_ms INTEGER
);

CREATE TABLE IF NOT EXISTS stock_factor_scores (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL,
    ticker VARCHAR(32),
    company_name TEXT,
    sector VARCHAR(128),

    fundamental_quality_score NUMERIC,
    valuation_score NUMERIC,
    momentum_score NUMERIC,
    analyst_score NUMERIC,
    financial_risk_score NUMERIC,
    quantitative_alpha_score NUMERIC,
    combined_portfolio_score NUMERIC,
    data_coverage_pct NUMERIC,

    selection_status VARCHAR(32),
    selection_reason TEXT,
    expected_return_original NUMERIC,
    expected_return_adjusted NUMERIC,
    final_portfolio_weight NUMERIC,

    raw_values_json JSONB,
    normalized_scores_json JSONB,
    effective_weights_json JSONB
);

CREATE TABLE IF NOT EXISTS mcp_tool_calls (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),

    request_id VARCHAR(128),
    tool_name VARCHAR(128),
    transport VARCHAR(64),
    server_url TEXT,

    status VARCHAR(32),
    runtime_ms INTEGER,
    error_message TEXT,

    request_type VARCHAR(64),
    symbol VARCHAR(32),
    strategy VARCHAR(128),
    sector VARCHAR(128),
    symbols_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_run_id ON backtest_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_symbol ON backtest_runs(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy ON backtest_runs(strategy);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_status ON backtest_runs(status);
CREATE INDEX IF NOT EXISTS idx_backtest_parameters_run_id ON backtest_parameters(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_id ON backtest_trades(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol ON backtest_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_strategy ON backtest_trades(strategy);
CREATE INDEX IF NOT EXISTS idx_equity_points_run_id ON equity_points(run_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_runs_created_at ON portfolio_optimization_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_portfolio_runs_run_id ON portfolio_optimization_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_runs_objective ON portfolio_optimization_runs(objective);
CREATE INDEX IF NOT EXISTS idx_portfolio_runs_sector ON portfolio_optimization_runs(sector);
CREATE INDEX IF NOT EXISTS idx_portfolio_runs_status ON portfolio_optimization_runs(status);
CREATE INDEX IF NOT EXISTS idx_portfolio_weights_run_id ON portfolio_weights(run_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_weights_sector ON portfolio_weights(sector);
CREATE INDEX IF NOT EXISTS idx_factor_runs_created_at ON factor_portfolio_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_factor_runs_run_id ON factor_portfolio_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_factor_runs_sector ON factor_portfolio_runs(sector);
CREATE INDEX IF NOT EXISTS idx_factor_runs_selection_method ON factor_portfolio_runs(selection_method);
CREATE INDEX IF NOT EXISTS idx_stock_factor_scores_run_id ON stock_factor_scores(run_id);
CREATE INDEX IF NOT EXISTS idx_stock_factor_scores_ticker ON stock_factor_scores(ticker);
CREATE INDEX IF NOT EXISTS idx_stock_factor_scores_sector ON stock_factor_scores(sector);
CREATE INDEX IF NOT EXISTS idx_stock_factor_scores_combined ON stock_factor_scores(combined_portfolio_score);
CREATE INDEX IF NOT EXISTS idx_stock_factor_scores_status ON stock_factor_scores(selection_status);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_created_at ON mcp_tool_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_tool_name ON mcp_tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_status ON mcp_tool_calls(status);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_symbol ON mcp_tool_calls(symbol);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_strategy ON mcp_tool_calls(strategy);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_sector ON mcp_tool_calls(sector);

GRANT CONNECT ON DATABASE analytics TO metabase_reader;
GRANT USAGE ON SCHEMA public TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO metabase_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO metabase_reader;
