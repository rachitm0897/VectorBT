from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from schemas.strategies import StrategyDetailsRequest, StrategySearchRequest
from schemas.strategies import ExecutionType, ReadinessStatus
from services.persistence import PersistenceService
from services.strategy_registry import StrategyRegistryService


class RegistrySearchWorkflow:
    def __init__(self) -> None:
        self.registry = StrategyRegistryService()
        self.persistence = PersistenceService()

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = StrategySearchRequest.model_validate(payload)
        strategies = self.registry.search(request)
        all_strategies = self.registry.all_strategies()
        return {
            "status": "success",
            "count": len(strategies),
            "total_count": len(all_strategies),
            "summary": _registry_summary(all_strategies, self.registry.import_status()),
            "strategies": [_compact_strategy(strategy) for strategy in strategies],
        }

    def details(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = StrategyDetailsRequest.model_validate(payload)
        strategy = self.registry.get(request.strategy_id)
        return {"status": "success", "strategy": strategy.model_dump(mode="json", exclude_none=True)}

    def sync_import(self) -> dict[str, Any]:
        result = self.registry.sync_import()
        persistence = self.persistence.persist_strategies(result.imported)
        all_strategies = self.registry.all_strategies(refresh=True)
        return {
            "status": "success",
            "import": result.to_dict(),
            "summary": _registry_summary(all_strategies, self.registry.import_status()),
            "persistence": persistence,
        }


def _compact_strategy(strategy) -> dict[str, Any]:
    status = _strategy_status(strategy)
    return {
        "strategy_id": strategy.strategy_id,
        "name": strategy.name,
        "aliases": strategy.aliases,
        "family": strategy.family,
        "description": strategy.description,
        "source_type": strategy.source_type,
        "horizon_bucket": strategy.horizon_bucket,
        "execution_type": strategy.execution_type,
        "readiness": strategy.readiness,
        "runnable": _is_executable(strategy),
        "executable": _is_executable(strategy),
        "usability_status": status,
        "status_label": _status_label(status),
        "long_only": strategy.long_only,
        "long_short": strategy.long_short,
        "template_hint": strategy.template_hint,
        "final_score": strategy.final_score,
        "active": strategy.active,
        "deprecated": strategy.deprecated,
    }


def _registry_summary(strategies: list[Any], import_status: dict[str, Any]) -> dict[str, Any]:
    status_counts = Counter(_strategy_status(strategy) for strategy in strategies)
    readiness_counts = Counter(str(strategy.readiness) for strategy in strategies)
    execution_counts = Counter(str(strategy.execution_type) for strategy in strategies)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_strategies": len(strategies),
        "executable_strategies": status_counts["executable"],
        "catalogue_only_strategies": status_counts["catalogue_only"],
        "imported_strategies": import_status.get("imported_strategies", 0),
        "built_in_strategies": import_status.get("built_in_strategies", 0),
        "failed_imports": import_status.get("failed_imports", 0),
        "missing_data_strategies": status_counts["missing_data"],
        "incomplete_rule_strategies": status_counts["incomplete_rules"],
        "failed_strategies": status_counts["failed"],
        "deprecated_strategies": status_counts["deprecated"],
        "readiness_counts": dict(readiness_counts),
        "execution_type_counts": dict(execution_counts),
        "import": import_status,
    }


def _strategy_status(strategy: Any) -> str:
    if strategy.deprecated or strategy.readiness == ReadinessStatus.DEPRECATED:
        return "deprecated"
    if strategy.readiness == ReadinessStatus.MISSING_DATA:
        return "missing_data"
    if strategy.readiness == ReadinessStatus.RULES_INCOMPLETE:
        return "incomplete_rules"
    if strategy.readiness == ReadinessStatus.BACKTEST_FAILED:
        return "failed"
    if _is_executable(strategy):
        return "executable"
    return "catalogue_only"


def _is_executable(strategy: Any) -> bool:
    return (
        bool(strategy.active)
        and not bool(strategy.deprecated)
        and strategy.readiness == ReadinessStatus.BACKTEST_READY
        and strategy.execution_type == ExecutionType.SINGLE_ASSET_SIGNAL
    )


def _status_label(status: str) -> str:
    return {
        "executable": "Executable",
        "catalogue_only": "Catalogue-only",
        "missing_data": "Missing data",
        "incomplete_rules": "Incomplete rules",
        "failed": "Failed",
        "deprecated": "Deprecated",
    }.get(status, status.replace("_", " ").title())
