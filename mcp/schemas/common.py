from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class WorkflowStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL_SUCCESS = "partial_success"


Lookback = Literal["1mo", "6mo", "1y", "2y", "5y"]
Resolution = Literal["D"]


class RequestContext(StrictModel):
    user_id: str | None = None
    session_id: str | None = None
    idempotency_key: str | None = None


class DataQuality(FlexibleModel):
    candles_fetched: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    cache_status: str | None = None
    warnings: list[str] = Field(default_factory=list)


def model_dump_jsonable(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)
