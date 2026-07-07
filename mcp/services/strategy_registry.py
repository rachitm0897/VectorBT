from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.settings import get_settings
from schemas.strategies import (
    CanonicalStrategy,
    ExecutionType,
    ReadinessStatus,
    StrategySearchRequest,
    StrategySource,
)
from services.strategy_importer import StrategyImportResult, StrategyImporter
from tools.strategies import STRATEGY_REGISTRY, strategy_schema


class StrategyRegistryService:
    def __init__(self, profiling_root: Path | None = None) -> None:
        settings = get_settings()
        self.profiling_root = profiling_root or settings.stock_strategy_profiling_root
        self.importer = StrategyImporter()

    def all_strategies(self, refresh: bool = False) -> list[CanonicalStrategy]:
        if refresh:
            _load_all_strategies.cache_clear()
        return _load_all_strategies(str(self.profiling_root))

    def sync_import(self) -> StrategyImportResult:
        _load_all_strategies.cache_clear()
        return self.importer.import_from_stock_strategy_profilling(self.profiling_root)

    def get(self, strategy_id: str) -> CanonicalStrategy:
        normalized = _normalize_id(strategy_id)
        for strategy in self.all_strategies():
            aliases = {_normalize_id(alias) for alias in strategy.aliases}
            if _normalize_id(strategy.strategy_id) == normalized or normalized in aliases:
                return strategy
        raise ValueError(f"Unknown strategy '{strategy_id}'.")

    def search(self, request: StrategySearchRequest) -> list[CanonicalStrategy]:
        query = (request.query or "").strip().lower()
        results: list[CanonicalStrategy] = []
        for strategy in self.all_strategies():
            if request.family and strategy.family.lower() != request.family.lower():
                continue
            if request.readiness and strategy.readiness != request.readiness:
                continue
            if request.execution_type and strategy.execution_type != request.execution_type:
                continue
            if request.executable_only and not strategy.runnable:
                continue
            if query:
                haystack = " ".join(
                    [
                        strategy.strategy_id,
                        strategy.name,
                        strategy.description,
                        strategy.family,
                        " ".join(strategy.aliases),
                    ]
                ).lower()
                if query not in haystack:
                    continue
            results.append(strategy)
        results = sorted(results, key=lambda item: (item.family, item.name))
        return results[: request.limit]


@lru_cache(maxsize=4)
def _load_all_strategies(profiling_root: str) -> list[CanonicalStrategy]:
    strategies = _prototype_strategies()
    imported, _failures = _load_imported_strategies(Path(profiling_root))
    existing = {strategy.strategy_id for strategy in strategies}
    strategies.extend(strategy for strategy in imported if strategy.strategy_id not in existing)
    return strategies


def _load_imported_strategies(root: Path) -> tuple[list[CanonicalStrategy], list[dict[str, Any]]]:
    return StrategyImporter().import_from_stock_strategy_profilling(root).imported, []


def _prototype_strategies() -> list[CanonicalStrategy]:
    output: list[CanonicalStrategy] = []
    for strategy_id, definition in STRATEGY_REGISTRY.items():
        schema = strategy_schema(strategy_id)
        properties: dict[str, Any] = {}
        defaults: dict[str, Any] = {}
        for name, field_schema in schema.items():
            field_type = field_schema.get("type", "number")
            properties[name] = {
                "type": field_type,
                "minimum": field_schema.get("min"),
                "maximum": field_schema.get("max"),
                "default": field_schema.get("default"),
            }
            defaults[name] = field_schema.get("default")
        output.append(
            CanonicalStrategy(
                strategy_id=strategy_id,
                name=str(definition["display_name"]),
                aliases=[strategy_id.replace("_", " "), strategy_id],
                description=str(definition["description"]),
                family="Technical",
                category="Technical Trading",
                source_type="built_in",
                source_references=[
                    StrategySource(source_type="code", name="tools.strategies", path="mcp/tools/strategies.py")
                ],
                horizon_bucket="Fast",
                required_data=["open", "high", "low", "close", "volume"],
                required_features=["close"],
                parameter_schema={
                    "type": "object",
                    "properties": properties,
                    "additionalProperties": False,
                },
                default_parameters=defaults,
                signal_rules={"runner": strategy_id},
                execution_type=ExecutionType.SINGLE_ASSET_SIGNAL,
                long_only=True,
                long_short=False,
                readiness=ReadinessStatus.BACKTEST_READY,
                implementation_version="built-in-v1",
                template_hint="single_stock_research",
                active=True,
                deprecated=False,
                source_hash=f"built_in:{strategy_id}:v1",
            )
        )
    return output


def _normalize_id(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

