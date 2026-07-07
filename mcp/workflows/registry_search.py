from __future__ import annotations

from typing import Any

from schemas.strategies import StrategyDetailsRequest, StrategySearchRequest
from services.persistence import PersistenceService
from services.strategy_registry import StrategyRegistryService


class RegistrySearchWorkflow:
    def __init__(self) -> None:
        self.registry = StrategyRegistryService()
        self.persistence = PersistenceService()

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = StrategySearchRequest.model_validate(payload)
        strategies = self.registry.search(request)
        return {
            "status": "success",
            "count": len(strategies),
            "strategies": [_compact_strategy(strategy) for strategy in strategies],
        }

    def details(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = StrategyDetailsRequest.model_validate(payload)
        strategy = self.registry.get(request.strategy_id)
        return {"status": "success", "strategy": strategy.model_dump(mode="json", exclude_none=True)}

    def sync_import(self) -> dict[str, Any]:
        result = self.registry.sync_import()
        persistence = self.persistence.persist_strategies(result.imported)
        return {"status": "success", "import": result.to_dict(), "persistence": persistence}


def _compact_strategy(strategy) -> dict[str, Any]:
    return {
        "strategy_id": strategy.strategy_id,
        "name": strategy.name,
        "aliases": strategy.aliases,
        "family": strategy.family,
        "description": strategy.description,
        "horizon_bucket": strategy.horizon_bucket,
        "execution_type": strategy.execution_type,
        "readiness": strategy.readiness,
        "runnable": strategy.runnable,
        "long_only": strategy.long_only,
        "long_short": strategy.long_short,
        "template_hint": strategy.template_hint,
        "final_score": strategy.final_score,
    }

