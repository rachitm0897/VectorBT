from __future__ import annotations

from typing import Any

from schemas.results import ResearchResultEnvelope
from schemas.ui import UITemplateSpec


ALLOWED_TEMPLATES = {
    "single_stock_research",
    "optimized_multi_stock_portfolio",
    "strategy_comparison",
    "strategy_catalogue_details",
    "monte_carlo_deep_dive",
    "discovery_candidate_review",
    "universe_backtest_classification",
    "error_data_quality_report",
}


class UISpecBuilder:
    def build_for_envelope(self, envelope: ResearchResultEnvelope) -> dict[str, Any]:
        if envelope.status == "error":
            template_id = "error_data_quality_report"
        elif envelope.workflow_type == "single_stock_research":
            template_id = "single_stock_research"
        elif envelope.workflow_type == "multi_stock_research":
            template_id = "optimized_multi_stock_portfolio"
        elif envelope.workflow_type == "strategy_comparison":
            template_id = "strategy_comparison"
        else:
            template_id = envelope.ui_hint or "strategy_catalogue_details"
        return self.build(template_id, envelope).model_dump(mode="json", exclude_none=True)

    def build(self, template_id: str, envelope: ResearchResultEnvelope) -> UITemplateSpec:
        if template_id not in ALLOWED_TEMPLATES:
            template_id = "error_data_quality_report"
        return UITemplateSpec(
            template_id=template_id,
            title=_title(template_id),
            props={
                "run_id": envelope.run_id,
                "workflow_type": envelope.workflow_type,
                "strategy": envelope.strategy,
                "universe": envelope.universe,
                "summary": envelope.summary,
                "metrics": envelope.metrics,
                "allocations": envelope.allocations,
                "trades": _compact_list(envelope.trades, 200),
                "equity": _downsample(envelope.equity, 500),
                "drawdown": _downsample(envelope.drawdown, 500),
                "monte_carlo": _compact_monte_carlo(envelope.monte_carlo),
                "frontier": _downsample(envelope.frontier, 300),
                "warnings": envelope.warnings,
                "errors": envelope.errors,
            },
            artifacts=[artifact.model_dump(mode="json", exclude_none=True) for artifact in envelope.artifacts],
            warnings=envelope.warnings,
        )


def _title(template_id: str) -> str:
    return template_id.replace("_", " ").title()


def _compact_list(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[:limit] if isinstance(rows, list) else []


def _downsample(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) <= limit:
        return rows if isinstance(rows, list) else []
    step = max(1, len(rows) // limit)
    return rows[::step][:limit]


def _compact_monte_carlo(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    compact = dict(payload)
    if isinstance(compact.get("percentile_paths"), dict):
        compact["percentile_paths"] = {
            key: values[:: max(1, len(values) // 300)][:300] if isinstance(values, list) else values
            for key, values in compact["percentile_paths"].items()
        }
    return compact
