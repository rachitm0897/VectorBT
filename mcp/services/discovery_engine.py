from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.settings import get_settings
from schemas.discovery import (
    CandidateReviewRequest,
    DiscoverySearchRequest,
    ProcessApprovedStrategyRequest,
)


class DiscoveryEngine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = self.settings.stock_strategy_profiling_root

    def discover_candidates(self, request: DiscoverySearchRequest) -> dict[str, Any]:
        if not self.root.exists():
            return {
                "status": "error",
                "message": "stock_strategy_profilling root not found.",
                "errors": ["profiling_repo_missing"],
            }
        try:
            sys.path.insert(0, str(self.root / "src"))
            from strategy_lab.config import ProjectConfig
            from strategy_lab.discovery.orchestrator import DiscoveryPipeline

            config = ProjectConfig.load(self.root / "config" / "config.yaml")
            pipeline = DiscoveryPipeline(config)
            candidates = pipeline.run(
                queries=[request.query],
                sources=list(request.sources),
                max_results_per_source=request.max_results_per_source,
                max_candidates=request.max_candidates,
                start_year=request.start_year,
                end_year=request.end_year,
            )
            return {"status": "success", "candidates": candidates, "count": len(candidates)}
        except Exception as exc:
            return {
                "status": "error",
                "message": str(exc),
                "errors": ["discovery_failed"],
            }
        finally:
            root_src = str(self.root / "src")
            if sys.path and sys.path[0] == root_src:
                sys.path.pop(0)

    def review_candidate(self, request: CandidateReviewRequest) -> dict[str, Any]:
        candidate_path = self._candidate_path(request.candidate_id)
        if not candidate_path.exists():
            return {"status": "error", "message": "Candidate not found.", "errors": ["candidate_not_found"]}
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        payload.setdefault("reviews", []).append(
            {
                "reviewed_at": datetime.now(UTC).isoformat(),
                "reviewer": request.reviewer,
                "action": request.action,
                "reviewer_note": request.reviewer_note,
                "edits": request.edits,
            }
        )
        if request.edits and isinstance(payload.get("candidate"), dict):
            payload["candidate"].update(request.edits)
        if request.action == "approve":
            payload["status"] = "APPROVED"
            destination = self.root / "catalogue" / "approved" / candidate_path.name
        elif request.action == "reject":
            payload["status"] = "REJECTED"
            destination = self.root / "catalogue" / "rejected" / candidate_path.name
        elif request.action == "mark_duplicate":
            payload["status"] = "DUPLICATE"
            destination = candidate_path
        else:
            payload["status"] = payload.get("status") or "PENDING_REVIEW"
            destination = candidate_path

        candidate_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        if destination != candidate_path:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate_path), str(destination))
        return {"status": "success", "candidate": payload}

    def process_approved_strategy(self, request: ProcessApprovedStrategyRequest) -> dict[str, Any]:
        approved_path = self.root / "catalogue" / "approved" / f"{request.candidate_id}.json"
        if not approved_path.exists():
            approved_path = self.root / "catalogue" / "approved" / request.candidate_id
        if not approved_path.exists():
            return {"status": "error", "message": "Approved candidate not found.", "errors": ["candidate_not_found"]}
        return {
            "status": "error",
            "message": (
                "Approved candidate processing requires the profiling repo feature panels and "
                "pipeline runtime. This MCP wrapper records review state but does not fabricate "
                "backtest or promotion results."
            ),
            "errors": ["approved_processing_not_configured"],
            "candidate_id": request.candidate_id,
        }

    def _candidate_path(self, candidate_id: str) -> Path:
        name = candidate_id if candidate_id.endswith(".json") else f"{candidate_id}.json"
        for directory in (
            self.root / "catalogue" / "candidates",
            self.root / "outputs" / "discovery_pending",
            self.root / "catalogue" / "approved",
            self.root / "catalogue" / "rejected",
        ):
            path = directory / name
            if path.exists():
                return path
        return self.root / "catalogue" / "candidates" / name

