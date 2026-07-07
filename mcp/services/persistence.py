from __future__ import annotations

from typing import Any

from app.settings import get_settings
from repositories.artifact_repo import ArtifactRepository
from repositories.run_repo import RunRepository
from repositories.strategy_repo import StrategyRepository
from schemas.results import ResearchResultEnvelope
from schemas.strategies import CanonicalStrategy


class PersistenceService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.strategy_repo = StrategyRepository()
        self.run_repo = RunRepository()
        self.artifact_repo = ArtifactRepository()

    def persist_strategies(self, strategies: list[CanonicalStrategy]) -> dict[str, Any]:
        if not self.settings.analytics_enabled:
            return {"enabled": False, "saved": False, "reason": "analytics_disabled"}
        try:
            return {"enabled": True, **self.strategy_repo.upsert_many(strategies)}
        except Exception as exc:
            return {"enabled": True, "saved": False, "error": str(exc)}

    def persist_research_result(self, envelope: ResearchResultEnvelope) -> dict[str, Any]:
        if not self.settings.analytics_enabled:
            return {"enabled": False, "saved": False, "reason": "analytics_disabled"}
        try:
            payload = envelope.model_dump(mode="json", exclude_none=True)
            run_result = self.run_repo.save_research_run(payload)
            for artifact in payload.get("artifacts") or []:
                self.artifact_repo.save_artifact(artifact, run_id=payload.get("run_id"))
            return {"enabled": True, **run_result}
        except Exception as exc:
            return {"enabled": True, "saved": False, "error": str(exc)}

    def get_research_run(self, run_id: str) -> dict[str, Any] | None:
        if not self.settings.analytics_enabled:
            return None
        return self.run_repo.get_research_run(run_id)

    def list_research_runs(self, limit: int = 25) -> list[dict[str, Any]]:
        if not self.settings.analytics_enabled:
            return []
        return self.run_repo.list_research_runs(limit=limit)
