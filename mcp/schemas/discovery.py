from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from schemas.common import StrictModel


class DiscoverySearchRequest(StrictModel):
    query: str
    sources: list[Literal["openalex", "crossref", "arxiv"]] = Field(
        default_factory=lambda: ["openalex", "crossref", "arxiv"]
    )
    max_results_per_source: int = Field(default=10, ge=1, le=50)
    max_candidates: int = Field(default=20, ge=1, le=100)
    start_year: int | None = None
    end_year: int | None = None


class CandidateReviewRequest(StrictModel):
    candidate_id: str
    action: Literal["approve", "reject", "mark_duplicate", "edit"]
    reviewer: str | None = None
    reviewer_note: str = ""
    edits: dict[str, Any] = Field(default_factory=dict)


class ProcessApprovedStrategyRequest(StrictModel):
    candidate_id: str
    limit: int = Field(default=1, ge=1, le=25)

