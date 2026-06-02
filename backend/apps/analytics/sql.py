CREATE_BACKTEST_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    source VARCHAR(32),
    status VARCHAR(32),
    error_message TEXT,
    symbol VARCHAR(20),
    strategy VARCHAR(64),
    lookback VARCHAR(20),
    resolution VARCHAR(10),
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
    llm_calls INTEGER,
    parser_cache VARCHAR(20),
    estimated_prompt_tokens INTEGER,
    estimated_output_tokens INTEGER,
    cache_status VARCHAR(20),
    candles_fetched INTEGER,
    request_json JSONB,
    metrics_json JSONB,
    summary_json JSONB,
    diagnostics_json JSONB
);
"""

CREATE_BACKTEST_PARAMETERS_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_parameters (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    parameter_name VARCHAR(64),
    parameter_value VARCHAR(128)
);
"""

CREATE_BACKTEST_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_trades (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(20),
    strategy VARCHAR(64),
    entry_time TIMESTAMP NULL,
    exit_time TIMESTAMP NULL,
    side VARCHAR(16),
    entry_price NUMERIC,
    exit_price NUMERIC,
    pnl NUMERIC,
    return_pct NUMERIC,
    duration_days INTEGER,
    status VARCHAR(32)
);
"""

CREATE_EQUITY_POINTS_TABLE = """
CREATE TABLE IF NOT EXISTS equity_points (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    time TIMESTAMP,
    strategy_equity NUMERIC,
    buy_hold_equity NUMERIC,
    spy_equity NUMERIC,
    drawdown_pct NUMERIC
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_backtest_runs_symbol ON backtest_runs(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy ON backtest_runs(strategy);",
    "CREATE INDEX IF NOT EXISTS idx_backtest_runs_status ON backtest_runs(status);",
    "CREATE INDEX IF NOT EXISTS idx_backtest_parameters_run_id ON backtest_parameters(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_id ON backtest_trades(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_equity_points_run_id ON equity_points(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_equity_points_time ON equity_points(time);",
]

SCHEMA_STATEMENTS = [
    CREATE_BACKTEST_RUNS_TABLE,
    CREATE_BACKTEST_PARAMETERS_TABLE,
    CREATE_BACKTEST_TRADES_TABLE,
    CREATE_EQUITY_POINTS_TABLE,
    *CREATE_INDEXES,
]

