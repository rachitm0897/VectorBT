from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from schemas.strategies import (
    CanonicalStrategy,
    ExecutionType,
    ReadinessStatus,
    StrategySource,
)


def load_catalogue_strategies(root: Path) -> tuple[list[CanonicalStrategy], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    if not root.exists():
        return [], [{"path": str(root), "message": "stock_strategy_profilling root not found"}]

    summary_by_id = _load_catalogue_summary(root)
    strategy_dir = root / "catalogue" / "strategies"
    if strategy_dir.exists():
        strategies = []
        for path in sorted(strategy_dir.glob("*.json")):
            try:
                payload = _read_json(path)
                strategies.append(_canonical_from_processed_payload(payload, path, summary_by_id))
            except Exception as exc:
                failures.append({"path": str(path), "message": str(exc)})
        return strategies, failures

    input_path = root / "inputs" / "strategy_definitions.json"
    if not input_path.exists():
        return [], [{"path": str(input_path), "message": "strategy catalogue not found"}]

    payload = _read_json(input_path)
    strategies = []
    for raw in payload.get("strategies", []):
        try:
            strategies.append(_canonical_from_definition(raw, input_path, summary_by_id))
        except Exception as exc:
            failures.append({"strategy_id": raw.get("id"), "message": str(exc)})
    return strategies, failures


def _load_catalogue_summary(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "catalogue" / "catalogue.json"
    if path.exists():
        payload = _read_json(path)
        return {
            str(row.get("strategy_id") or row.get("id")): row
            for row in payload.get("strategies", [])
            if row.get("strategy_id") or row.get("id")
        }

    csv_path = root / "catalogue" / "catalogue.csv"
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {
                str(row.get("strategy_id") or row.get("Strategy ID")): row
                for row in csv.DictReader(handle)
                if row.get("strategy_id") or row.get("Strategy ID")
            }
    return {}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_from_processed_payload(
    payload: dict[str, Any],
    path: Path,
    summary_by_id: dict[str, dict[str, Any]],
) -> CanonicalStrategy:
    definition = payload.get("original_strategy_definition")
    if not isinstance(definition, dict):
        definition = payload.get("definition") if isinstance(payload.get("definition"), dict) else payload
    strategy_id = str(payload.get("strategy_id") or definition.get("id") or path.stem)
    summary = summary_by_id.get(strategy_id, {})
    status = str(payload.get("status") or summary.get("status") or "").upper()
    normalized_scores = payload.get("normalized_scores") if isinstance(payload.get("normalized_scores"), dict) else {}
    if not normalized_scores and isinstance(payload.get("variants"), list):
        for variant in payload["variants"]:
            if isinstance(variant, dict) and isinstance(variant.get("normalized_scores"), dict):
                normalized_scores = variant["normalized_scores"]
                break

    canonical = _canonical_from_definition(definition, path, summary_by_id)
    canonical.implementation_version = str(payload.get("strategy_version") or canonical.implementation_version)
    canonical.readiness = _readiness_from_status(status, canonical)
    canonical.classification_metrics = _first_dict(
        payload.get("horizon_metrics"),
        payload.get("classification"),
        summary,
    )
    canonical.return_score = _first_float(
        normalized_scores.get("return_score"),
        payload.get("return_score"),
        summary.get("return_score"),
    )
    canonical.risk_score = _first_float(
        normalized_scores.get("risk_score"),
        payload.get("risk_score"),
        summary.get("risk_score"),
    )
    canonical.risk_adjusted_score = _first_float(
        normalized_scores.get("risk_adjusted_score"),
        payload.get("risk_adjusted_score"),
        summary.get("risk_adjusted_score"),
    )
    canonical.robustness_score = _first_float(
        normalized_scores.get("robustness_score"),
        payload.get("robustness_score"),
        summary.get("robustness_score"),
    )
    canonical.final_score = _first_float(
        normalized_scores.get("final_risk_return_score"),
        normalized_scores.get("risk_return_score"),
        payload.get("final_risk_return_score"),
        summary.get("final_risk_return_score"),
    )
    canonical.source_payload = payload
    canonical.source_hash = _hash_payload(payload)
    return canonical


def _canonical_from_definition(
    raw: dict[str, Any],
    path: Path,
    summary_by_id: dict[str, dict[str, Any]],
) -> CanonicalStrategy:
    strategy_id = str(raw.get("id") or raw.get("strategy_id") or path.stem)
    summary = summary_by_id.get(strategy_id, {})
    screening_rules = raw.get("screening_rules") if isinstance(raw.get("screening_rules"), list) else []
    ranking_factors = raw.get("ranking_factors") if isinstance(raw.get("ranking_factors"), list) else []
    required_data = _string_list(raw.get("required_data"))
    required_features = sorted(
        set(required_data)
        | {str(rule.get("field")) for rule in screening_rules if isinstance(rule, dict) and rule.get("field")}
        | {str(factor.get("field")) for factor in ranking_factors if isinstance(factor, dict) and factor.get("field")}
    )
    execution_type = (
        ExecutionType.CROSS_SECTIONAL_RANKING
        if ranking_factors
        else ExecutionType.RESEARCH_ONLY
    )
    readiness = _readiness_from_status(str(summary.get("status") or "").upper(), None)
    if readiness == ReadinessStatus.RESEARCH_ONLY:
        readiness = ReadinessStatus.BACKTEST_READY if ranking_factors else ReadinessStatus.RULES_INCOMPLETE
    portfolio_direction = str(raw.get("portfolio_direction") or "").lower()
    scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    return CanonicalStrategy(
        strategy_id=strategy_id,
        name=str(raw.get("name") or raw.get("strategy_name") or strategy_id),
        aliases=_string_list(raw.get("aliases")),
        description=str(raw.get("description") or ""),
        family=str(raw.get("family") or "Unclassified"),
        category=str(raw.get("category") or "Unclassified"),
        source_type="stock_strategy_profilling",
        source_references=[
            StrategySource(
                source_type="file",
                name="stock_strategy_profilling",
                path=str(path),
            )
        ],
        horizon_bucket=summary.get("assigned_bucket") or raw.get("horizon_bucket"),
        required_data=required_data,
        required_features=required_features,
        parameter_schema={
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "portfolio_variant": {
                    "type": "string",
                    "enum": ["long_only", "long_short"],
                    "default": "long_only",
                },
            },
            "additionalProperties": False,
        },
        default_parameters={"top_n": 10, "portfolio_variant": "long_only"},
        ranking_rules={
            "screening_rules": screening_rules,
            "ranking_factors": ranking_factors,
            "entry_conditions": raw.get("entry_conditions") or "",
            "exit_conditions": raw.get("exit_conditions") or "",
            "rebalance_frequency": raw.get("rebalance_frequency") or raw.get("trading_frequency"),
        },
        execution_type=execution_type,
        long_only=portfolio_direction in {"", "both", "long_only"},
        long_short=portfolio_direction in {"both", "long_short"},
        readiness=readiness,
        implementation_version=str(raw.get("implementation_version") or "1"),
        classification_metrics={
            "typical_holding_months": raw.get("typical_holding_months"),
            "typical_holding_period": raw.get("typical_holding_period"),
            "signal_lifespan": raw.get("signal_lifespan"),
            "trading_frequency": raw.get("trading_frequency"),
            "confidence_score": summary.get("confidence_score"),
        },
        risk_score=_first_float(summary.get("risk_score")),
        return_score=_first_float(summary.get("return_score")),
        risk_adjusted_score=_first_float(summary.get("risk_adjusted_score")),
        robustness_score=_first_float(summary.get("robustness_score")),
        final_score=_first_float(summary.get("final_risk_return_score"), scores.get("overall_score_0_to_100")),
        template_hint="strategy_catalogue_details",
        active=True,
        deprecated=False,
        source_hash=_hash_payload(raw),
        source_payload=raw,
    )


def _readiness_from_status(status: str, strategy: CanonicalStrategy | None) -> ReadinessStatus:
    status = (status or "").upper()
    if status in {"BACKTESTED", "BACKTEST_READY"}:
        return ReadinessStatus.BACKTEST_READY
    if status == "MISSING_DATA":
        return ReadinessStatus.MISSING_DATA
    if status == "RULES_INCOMPLETE":
        return ReadinessStatus.RULES_INCOMPLETE
    if status == "BACKTEST_FAILED":
        return ReadinessStatus.BACKTEST_FAILED
    if strategy and strategy.execution_type == ExecutionType.RESEARCH_ONLY:
        return ReadinessStatus.RESEARCH_ONLY
    return ReadinessStatus.RESEARCH_ONLY


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(";") if part.strip()]
    return []


def _hash_payload(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _first_float(*values: Any) -> float | None:
    for value in values:
        try:
            if value is None or value == "":
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}
