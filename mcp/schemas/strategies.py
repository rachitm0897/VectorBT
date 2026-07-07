from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from schemas.common import FlexibleModel, StrictModel


class ExecutionType(StrEnum):
    SINGLE_ASSET_SIGNAL = "single_asset_signal"
    CROSS_SECTIONAL_RANKING = "cross_sectional_ranking"
    PORTFOLIO_STRATEGY = "portfolio_strategy"
    RESEARCH_ONLY = "research_only"


class ReadinessStatus(StrEnum):
    BACKTEST_READY = "BACKTEST_READY"
    MISSING_DATA = "MISSING_DATA"
    RULES_INCOMPLETE = "RULES_INCOMPLETE"
    BACKTEST_FAILED = "BACKTEST_FAILED"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    DEPRECATED = "DEPRECATED"


class StrategySource(FlexibleModel):
    source_type: str
    name: str | None = None
    url: str | None = None
    path: str | None = None
    citation: str | None = None


class StrategyRule(FlexibleModel):
    field: str
    op: str
    value: Any
    why: str | None = None


class RankingFactor(FlexibleModel):
    field: str
    direction: str = "high"
    weight: float = 1.0


class CanonicalStrategy(FlexibleModel):
    strategy_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    family: str = "Unclassified"
    category: str | None = None
    source_type: str = "local"
    source_references: list[StrategySource] = Field(default_factory=list)
    horizon_bucket: str | None = None
    required_data: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    parameter_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    default_parameters: dict[str, Any] = Field(default_factory=dict)
    signal_rules: dict[str, Any] = Field(default_factory=dict)
    ranking_rules: dict[str, Any] = Field(default_factory=dict)
    execution_type: ExecutionType = ExecutionType.RESEARCH_ONLY
    long_only: bool = True
    long_short: bool = False
    readiness: ReadinessStatus = ReadinessStatus.RESEARCH_ONLY
    implementation_version: str = "1"
    classification_metrics: dict[str, Any] = Field(default_factory=dict)
    risk_score: float | None = None
    return_score: float | None = None
    risk_adjusted_score: float | None = None
    robustness_score: float | None = None
    final_score: float | None = None
    template_hint: str = "strategy_details"
    active: bool = True
    deprecated: bool = False
    source_hash: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def runnable(self) -> bool:
        return self.active and not self.deprecated and self.readiness == ReadinessStatus.BACKTEST_READY


class StrategySearchRequest(StrictModel):
    query: str | None = None
    family: str | None = None
    readiness: ReadinessStatus | None = None
    execution_type: ExecutionType | None = None
    executable_only: bool = False
    limit: int = Field(default=1000, ge=1, le=2000)


class StrategyDetailsRequest(StrictModel):
    strategy_id: str
