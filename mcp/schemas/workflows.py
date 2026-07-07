from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from schemas.common import Lookback, RequestContext, Resolution, StrictModel


class MonteCarloSettings(StrictModel):
    enabled: bool = True
    method: Literal["bootstrap", "block_bootstrap"] = "bootstrap"
    mode: Literal["strategy_returns", "portfolio_returns", "raw_asset_returns"] = "strategy_returns"
    days: int = Field(default=60, ge=1, le=252)
    simulations: int = Field(default=500, ge=10, le=5000)
    block_size: int = Field(default=5, ge=1, le=20)
    seed: int | None = 42
    thresholds: list[float] = Field(default_factory=lambda: [-0.10, -0.20])


class OptimizationSettings(StrictModel):
    objective: Literal["max_sharpe", "min_volatility", "target_return", "target_volatility"] = "max_sharpe"
    risk_free_rate: float = Field(default=0.0, ge=0.0, le=0.25)
    target_return: float | None = None
    target_volatility: float | None = None
    allow_short: bool = False
    min_weight: float | None = None
    max_weight: float = Field(default=0.6, gt=0.0, le=1.0)
    gross_exposure_limit: float = Field(default=1.0, gt=0.0, le=3.0)
    net_exposure: float = Field(default=1.0, ge=-1.0, le=1.0)
    covariance_regularization: float = Field(default=1e-6, ge=0.0, le=1.0)
    num_frontier_portfolios: int = Field(default=1000, ge=50, le=10000)


class SingleStockResearchRequest(StrictModel):
    context: RequestContext | None = None
    symbol: str = Field(min_length=1)
    strategy_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    lookback: Lookback = "2y"
    resolution: Resolution = "D"
    initial_cash: float = Field(default=10000, gt=0)
    fees: float = Field(default=0.001, ge=0)
    monte_carlo: MonteCarloSettings = Field(default_factory=MonteCarloSettings)
    benchmark: str | None = None
    finnhub_api_key: str | None = Field(default=None, exclude=True)


class MultiStockResearchRequest(StrictModel):
    context: RequestContext | None = None
    symbols: list[str] = Field(min_length=2, max_length=30)
    strategy_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    lookback: Lookback = "2y"
    resolution: Resolution = "D"
    initial_cash: float = Field(default=10000, gt=0)
    fees: float = Field(default=0.001, ge=0)
    optimization: OptimizationSettings = Field(default_factory=OptimizationSettings)
    monte_carlo: MonteCarloSettings = Field(default_factory=lambda: MonteCarloSettings(mode="portfolio_returns"))
    finnhub_api_key: str | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def normalize_monte_carlo_mode(self):
        self.monte_carlo.mode = "portfolio_returns"
        return self


class StrategyComparisonRequest(StrictModel):
    symbol: str
    strategy_ids: list[str] = Field(min_length=2, max_length=10)
    parameters_by_strategy: dict[str, dict[str, Any]] = Field(default_factory=dict)
    lookback: Lookback = "2y"
    resolution: Resolution = "D"
    initial_cash: float = Field(default=10000, gt=0)
    fees: float = Field(default=0.001, ge=0)
    finnhub_api_key: str | None = Field(default=None, exclude=True)

