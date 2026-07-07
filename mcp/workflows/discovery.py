from __future__ import annotations

from typing import Any

from schemas.discovery import (
    CandidateReviewRequest,
    DiscoverySearchRequest,
    ProcessApprovedStrategyRequest,
)
from services.discovery_engine import DiscoveryEngine


class DiscoveryWorkflow:
    def __init__(self) -> None:
        self.engine = DiscoveryEngine()

    def discover(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = DiscoverySearchRequest.model_validate(payload)
        return self.engine.discover_candidates(request)

    def review(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = CandidateReviewRequest.model_validate(payload)
        return self.engine.review_candidate(request)

    def process_approved(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = ProcessApprovedStrategyRequest.model_validate(payload)
        return self.engine.process_approved_strategy(request)

