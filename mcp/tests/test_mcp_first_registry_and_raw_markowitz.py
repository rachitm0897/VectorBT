from __future__ import annotations

import pandas as pd

from schemas.strategies import CanonicalStrategy, ExecutionType, ReadinessStatus
from tools.public import run_raw_markowitz_optimization
from workflows.registry_search import _compact_strategy


def test_imported_cross_sectional_strategy_is_visible_but_not_runnable():
    strategy = CanonicalStrategy(
        strategy_id="imported_ranker",
        name="Imported Ranker",
        source_type="stock_strategy_profilling",
        execution_type=ExecutionType.CROSS_SECTIONAL_RANKING,
        readiness=ReadinessStatus.BACKTEST_READY,
    )

    compact = _compact_strategy(strategy)

    assert compact["source_type"] == "stock_strategy_profilling"
    assert compact["usability_status"] == "catalogue_only"
    assert compact["runnable"] is False
    assert compact["executable"] is False


def test_raw_markowitz_optimization_uses_raw_asset_returns(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=80, freq="D", tz="UTC")
    prices = pd.DataFrame(
        {
            "AAPL": [100 + index * 0.3 for index in range(80)],
            "MSFT": [120 + index * 0.2 for index in range(80)],
            "NVDA": [90 + index * 0.4 for index in range(80)],
        },
        index=dates,
    )

    monkeypatch.setattr("services.market_data.MarketDataService.fetch_aligned_closes", lambda *args, **kwargs: prices)

    result = run_raw_markowitz_optimization(
        symbols=["AAPL", "MSFT", "NVDA"],
        optimization={
            "objective": "min_volatility",
            "allow_short": False,
            "max_weight": 0.8,
            "num_frontier_portfolios": 50,
        },
        monte_carlo={"enabled": True, "days": 20, "simulations": 20, "seed": 7},
    )

    assert result["status"] == "success"
    assert result["workflow_type"] == "raw_asset_markowitz"
    assert result["diagnostics"]["optimizer_input"] == "raw_asset_returns"
    assert result["monte_carlo"]["mode"] == "raw_asset_returns"
    assert result["allocations"]["weights"]
