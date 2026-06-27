from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field


StrategyName = str
Lookback = Literal["1mo", "6mo", "1y", "2y", "5y"]
Resolution = Literal["D"]
MonteCarloMethod = Literal["bootstrap"]
ScenarioName = Literal["neutral", "bullish", "bearish", "crash"]


def _default_initial_cash() -> float:
    return float(os.getenv("DEFAULT_INITIAL_CASH", "10000"))


def _default_fees() -> float:
    return float(os.getenv("DEFAULT_FEES", "0.001"))


class MarketDataRequest(BaseModel):
    symbol: str = Field(min_length=1)
    lookback: Lookback = "2y"
    resolution: Resolution = "D"
    finnhub_api_key: str | None = Field(default=None, exclude=True)


class StrategyBacktestRequest(MarketDataRequest):
    strategy: StrategyName
    parameters: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = Field(default_factory=_default_initial_cash, gt=0)
    fees: float = Field(default_factory=_default_fees, ge=0)


class IndicatorRequest(MarketDataRequest):
    indicator: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class IndicatorSpec(BaseModel):
    name: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    alias: str | None = Field(default=None, min_length=1)


class IndicatorBatchRequest(MarketDataRequest):
    indicators: list[IndicatorSpec] = Field(min_length=1, max_length=50)


class MonteCarloRequest(MarketDataRequest):
    start_value: float = Field(default=10000, gt=0)
    days: int = Field(default=60, ge=1, le=252)
    simulations: int = Field(default=500, ge=10, le=5000)
    method: MonteCarloMethod = "bootstrap"


class StrategyResearchRequest(StrategyBacktestRequest):
    run_monte_carlo: bool = True
    monte_carlo_days: int = Field(default=60, ge=1, le=252)
    monte_carlo_simulations: int = Field(default=500, ge=10, le=5000)


class PortfolioScenarioOverride(BaseModel):
    drift_shift_annual: float | None = Field(default=None, ge=-0.50, le=0.50)
    volatility_multiplier: float | None = Field(default=None, ge=0.25, le=4.0)
    initial_shock_pct: float | None = Field(default=None, ge=-0.80, le=0.80)


class MarkowitzOptimizationRequest(BaseModel):
    symbols: list[str] | None = None
    sector: str | None = None
    lookback: Lookback = "2y"
    resolution: Resolution = "D"
    objective: Literal["max_sharpe", "min_volatility"] = "max_sharpe"
    risk_free_rate: float = Field(default=0.0, ge=0.0, le=0.25)
    allow_short: bool = False
    max_weight: float = Field(default=0.6, ge=0.05, le=1.0)
    num_frontier_portfolios: int = Field(default=3000, ge=100, le=10000)
    run_monte_carlo: bool = False
    monte_carlo_days: int = Field(default=60, ge=1, le=252)
    monte_carlo_simulations: int = Field(default=500, ge=100, le=5000)
    monte_carlo_block_size: int = Field(default=5, ge=1, le=20)
    monte_carlo_seed: int | None = 42
    monte_carlo_scenarios: list[ScenarioName] = Field(
        default_factory=lambda: ["neutral", "bullish", "bearish", "crash"],
        min_length=1,
    )
    scenario_overrides: dict[ScenarioName, PortfolioScenarioOverride] = Field(default_factory=dict)
    finnhub_api_key: str | None = Field(default=None, exclude=True)


class FactorModelConfig(BaseModel):
    enabled: bool = True
    normalization_mode: Literal["universe", "sector"] = "sector"
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "fundamental_quality": 0.30,
            "valuation": 0.20,
            "momentum": 0.20,
            "analyst": 0.15,
            "financial_risk": 0.15,
        }
    )
    minimum_data_coverage_pct: float = Field(default=60, ge=0, le=100)
    selection_method: Literal["top_n", "top_percentile", "minimum_score", "all_eligible"] = "top_n"
    top_n: int = Field(default=10, ge=1, le=50)
    top_percentile: float = Field(default=30, ge=1, le=100)
    minimum_score: float | None = Field(default=None, ge=0, le=100)


class FactorOptimizationConfig(BaseModel):
    objective: Literal["max_sharpe", "min_volatility"] = "max_sharpe"
    minimum_weight: float = Field(default=0, ge=0, le=1)
    maximum_weight: float = Field(default=0.25, ge=0.05, le=1)
    risk_free_rate: float = Field(default=0.04, ge=0, le=0.25)
    expected_return_method: Literal["historical", "factor_tilted"] = "historical"
    num_frontier_portfolios: int = Field(default=3000, ge=100, le=10000)


class ScoreTiltConfig(BaseModel):
    enabled: bool = False
    strength: float = Field(default=0.20, ge=0, le=1)
    maximum_adjustment_pct: float = Field(default=0.05, ge=0, le=0.50)


class FactorMonteCarloConfig(BaseModel):
    enabled: bool = True
    days: int = Field(default=60, ge=1, le=252)
    simulations: int = Field(default=500, ge=100, le=5000)
    block_size: int = Field(default=5, ge=1, le=20)
    seed: int | None = 42
    scenarios: list[ScenarioName] = Field(
        default_factory=lambda: ["neutral", "bullish", "bearish", "crash"],
        min_length=1,
    )
    scenario_overrides: dict[ScenarioName, PortfolioScenarioOverride] = Field(default_factory=dict)


class FactorPortfolioRequest(BaseModel):
    symbols: list[str] | None = None
    sector: str | None = None
    selection_mode: Literal["symbols", "sector"] = "symbols"
    lookback: Lookback = "2y"
    resolution: Resolution = "D"
    factor_model: FactorModelConfig = Field(default_factory=FactorModelConfig)
    optimization: FactorOptimizationConfig = Field(default_factory=FactorOptimizationConfig)
    score_tilt: ScoreTiltConfig = Field(default_factory=ScoreTiltConfig)
    monte_carlo: FactorMonteCarloConfig = Field(default_factory=FactorMonteCarloConfig)
    finnhub_api_key: str | None = Field(default=None, exclude=True)


def parse_request(model: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    if hasattr(model, "model_validate"):
        return model.model_validate(payload)
    return model(**payload)


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
