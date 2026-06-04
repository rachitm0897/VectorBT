# Sample MCP Requests

## list_strategies

```json
{}
```

## get_strategy_schema

```json
{
  "strategy": "rsi_mean_reversion"
}
```

## fetch_market_data_summary

```json
{
  "symbol": "AAPL",
  "lookback": "2y",
  "resolution": "D"
}
```

## run_strategy_backtest

```json
{
  "symbol": "NVDA",
  "strategy": "rsi_mean_reversion",
  "parameters": {
    "rsi_window": 14,
    "lower": 30,
    "upper": 70
  },
  "lookback": "2y",
  "resolution": "D",
  "initial_cash": 10000,
  "fees": 0.001
}
```

## run_monte_carlo_simulation

```json
{
  "symbol": "AAPL",
  "lookback": "2y",
  "resolution": "D",
  "start_value": 10000,
  "days": 60,
  "simulations": 500,
  "method": "bootstrap"
}
```

## run_strategy_research

```json
{
  "symbol": "Apple",
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
