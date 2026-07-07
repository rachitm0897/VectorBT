from __future__ import annotations

from typing import Any

from pydantic import Field

from schemas.common import FlexibleModel


class ArtifactRef(FlexibleModel):
    artifact_id: str
    artifact_path: str | None = None
    artifact_url: str | None = None
    artifact_type: str = "json"
    summary: dict[str, Any] = Field(default_factory=dict)


class ResearchResultEnvelope(FlexibleModel):
    status: str
    workflow_type: str
    run_id: str | None = None
    strategy: dict[str, Any] | None = None
    strategy_version: str | None = None
    universe: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    data_quality: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    allocations: dict[str, Any] = Field(default_factory=dict)
    trades: list[dict[str, Any]] = Field(default_factory=list)
    equity: list[dict[str, Any]] = Field(default_factory=list)
    drawdown: list[dict[str, Any]] = Field(default_factory=list)
    monte_carlo: dict[str, Any] | None = None
    frontier: list[dict[str, Any]] = Field(default_factory=list)
    comparison: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    ui_hint: str | None = None
    ui_spec: dict[str, Any] | None = None
    persistence: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

