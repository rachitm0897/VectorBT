import json
import math

import pandas as pd
import pytest

from adapters.stock_strategy_profilling import load_catalogue_strategies
from app.errors import ReadinessError, ValidationFailedError
from schemas.strategies import CanonicalStrategy, ExecutionType, ReadinessStatus
from schemas.workflows import MonteCarloSettings, OptimizationSettings
from services.monte_carlo_engine import MonteCarloEngine
from services.portfolio_optimizer import PortfolioOptimizer
from services.strategy_validation import StrategyValidationService


def test_strategy_importer_normalizes_catalogue_strategy_and_hash_is_stable(tmp_path):
    strategy_dir = tmp_path / "catalogue" / "strategies"
    strategy_dir.mkdir(parents=True)
    payload = {
        "strategy_id": "quality_momentum_test",
        "status": "BACKTEST_READY",
        "original_strategy_definition": {
            "id": "quality_momentum_test",
            "name": "Quality Momentum Test",
            "description": "Ranks liquid equities by quality and momentum.",
            "family": "Quality",
            "required_data": ["roe", "price_momentum_12m"],
            "ranking_factors": [
                {"field": "roe", "direction": "high", "weight": 0.6},
                {"field": "price_momentum_12m", "direction": "high", "weight": 0.4},
            ],
            "portfolio_direction": "both",
        },
        "normalized_scores": {"final_risk_return_score": 73.5},
    }
    (strategy_dir / "quality_momentum_test.json").write_text(json.dumps(payload), encoding="utf-8")

    imported_once, failures_once = load_catalogue_strategies(tmp_path)
    imported_twice, failures_twice = load_catalogue_strategies(tmp_path)

    assert failures_once == []
    assert failures_twice == []
    assert len(imported_once) == 1
    strategy = imported_once[0]
    assert strategy.strategy_id == "quality_momentum_test"
    assert strategy.execution_type == ExecutionType.CROSS_SECTIONAL_RANKING
    assert strategy.readiness == ReadinessStatus.BACKTEST_READY
    assert strategy.long_short is True
    assert strategy.final_score == 73.5
    assert strategy.source_hash == imported_twice[0].source_hash


def test_strategy_parameter_validation_rejects_unknown_properties():
    strategy = CanonicalStrategy(
        strategy_id="strict_params",
        name="Strict Params",
        readiness=ReadinessStatus.BACKTEST_READY,
        execution_type=ExecutionType.SINGLE_ASSET_SIGNAL,
        parameter_schema={
            "type": "object",
            "properties": {"window": {"type": "integer", "minimum": 2}},
            "additionalProperties": False,
        },
        default_parameters={"window": 20},
    )

    validator = StrategyValidationService()

    assert validator.validate_parameters(strategy, {"window": 30}) == {"window": 30}
    with pytest.raises(ValidationFailedError):
        validator.validate_parameters(strategy, {"window": 30, "unsupported": True})


def test_strategy_readiness_filter_blocks_cross_sectional_strategy_for_single_asset_workflow():
    strategy = CanonicalStrategy(
        strategy_id="ranking_only",
        name="Ranking Only",
        readiness=ReadinessStatus.BACKTEST_READY,
        execution_type=ExecutionType.CROSS_SECTIONAL_RANKING,
    )

    with pytest.raises(ReadinessError) as exc_info:
        StrategyValidationService().validate_runnable(
            strategy,
            required_execution_type=ExecutionType.SINGLE_ASSET_SIGNAL,
        )

    assert exc_info.value.code == "unsupported_execution_type"


def test_strategy_return_monte_carlo_engine_exposes_workflow_distribution_fields():
    result = MonteCarloEngine().simulate_returns(
        pd.Series([0.01, -0.005, 0.002, 0.004, -0.001, 0.006]),
        start_value=10000,
        settings=MonteCarloSettings(
            mode="strategy_returns",
            days=12,
            simulations=100,
            seed=7,
            thresholds=[-0.05],
        ),
    )

    assert result["mode"] == "strategy_returns"
    assert result["simulation_count"] == 100
    assert result["horizon"] == 12
    assert set(result["percentile_paths"]) == {"p5", "p25", "p50", "p75", "p95"}
    assert "probability_of_loss_pct" in result
    assert "expected_shortfall_pct" in result
    assert "-0.05" in result["threshold_breach_probabilities_pct"]


def test_portfolio_optimizer_supports_long_only_and_singular_covariance():
    returns = pd.DataFrame(
        {
            "AAPL": [0.01, 0.01, -0.002, 0.004, 0.006, 0.003],
            "MSFT": [0.01, 0.01, -0.002, 0.004, 0.006, 0.003],
            "NVDA": [0.012, -0.004, 0.006, 0.008, -0.001, 0.007],
        }
    )
    result = PortfolioOptimizer().optimize_returns(
        returns,
        OptimizationSettings(
            objective="min_volatility",
            allow_short=False,
            max_weight=0.8,
            covariance_regularization=1e-5,
            num_frontier_portfolios=50,
        ),
    )

    weights = result["weights"]
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-5)
    assert all(0 <= weight <= 0.8 for weight in weights.values())
    assert result["metrics"]["annual_volatility_pct"] >= 0
    assert result["correlation_matrix"]


def test_portfolio_optimizer_honors_bounded_long_short_constraints():
    returns = pd.DataFrame(
        {
            "AAPL": [0.015, -0.01, 0.012, -0.004, 0.009, 0.003],
            "MSFT": [0.004, 0.002, 0.001, 0.003, -0.002, 0.001],
            "NVDA": [-0.01, 0.014, -0.006, 0.011, -0.003, 0.008],
        }
    )
    result = PortfolioOptimizer().optimize_returns(
        returns,
        OptimizationSettings(
            objective="max_sharpe",
            allow_short=True,
            min_weight=-0.4,
            max_weight=0.8,
            gross_exposure_limit=1.4,
            net_exposure=1.0,
            covariance_regularization=1e-6,
            num_frontier_portfolios=50,
        ),
    )

    weights = result["weights"]
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-5)
    assert sum(abs(weight) for weight in weights.values()) <= 1.40001
    assert all(-0.40001 <= weight <= 0.80001 for weight in weights.values())
    assert result["metrics"]["gross_exposure"] <= 1.40001
