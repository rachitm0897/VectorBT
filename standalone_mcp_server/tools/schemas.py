from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field


StrategyName = Literal["sma_crossover", "rsi_mean_reversion", "bollinger_reversion"]
Lookback = Literal["1mo", "6mo", "1y", "2y", "5y"]
Resolution = Literal["D"]
MonteCarloMethod = Literal["bootstrap"]


def _default_initial_cash() -> float:
    return float(os.getenv("DEFAULT_INITIAL_CASH", "10000"))


def _default_fees() -> float:
    return float(os.getenv("DEFAULT_FEES", "0.001"))


class MarketDataRequest(BaseModel):
    symbol: str = Field(min_length=1)
    lookback: Lookback = "2y"
    resolution: Resolution = "D"


class StrategyBacktestRequest(MarketDataRequest):
    strategy: StrategyName
    parameters: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = Field(default_factory=_default_initial_cash, gt=0)
    fees: float = Field(default_factory=_default_fees, ge=0)


class MonteCarloRequest(MarketDataRequest):
    start_value: float = Field(default=10000, gt=0)
    days: int = Field(default=60, ge=1, le=252)
    simulations: int = Field(default=500, ge=10, le=5000)
    method: MonteCarloMethod = "bootstrap"


class StrategyResearchRequest(StrategyBacktestRequest):
    run_monte_carlo: bool = True
    monte_carlo_days: int = Field(default=60, ge=1, le=252)
    monte_carlo_simulations: int = Field(default=500, ge=10, le=5000)


def parse_request(model: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    if hasattr(model, "model_validate"):
        return model.model_validate(payload)
    return model(**payload)


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
