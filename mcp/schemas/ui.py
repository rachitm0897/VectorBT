from __future__ import annotations

from typing import Any

from pydantic import Field

from schemas.common import StrictModel


class UITemplateSpec(StrictModel):
    template_id: str
    title: str | None = None
    props: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
