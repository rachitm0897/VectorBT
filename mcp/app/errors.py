from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

logger = logging.getLogger("vectorbt_mcp")


class ResearchError(Exception):
    code = "research_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code or self.code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(ResearchError):
    code = "not_found"


class ValidationFailedError(ResearchError):
    code = "validation_failed"


class ReadinessError(ResearchError):
    code = "strategy_not_ready"


class ExternalServiceError(ResearchError):
    code = "external_service_error"


class PersistenceError(ResearchError):
    code = "persistence_error"


def error_response(message: str, errors: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    return {"status": "error", "message": message, "errors": errors or ["unknown_error"], **extra}


def validation_error_response(exc: ValidationError) -> dict[str, Any]:
    codes: list[str] = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err.get("loc", []))
        code = err.get("type", "validation_error")
        codes.append(f"{location}:{code}" if location else code)
    return error_response("Invalid request parameters.", codes or ["validation_error"])


def exception_response(context: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ResearchError):
        return error_response(str(exc), [exc.code], details=exc.details)
    if isinstance(exc, ValidationError):
        return validation_error_response(exc)
    if isinstance(exc, ValueError):
        message = str(exc)
        code = "missing_finnhub_api_key" if message == "Finnhub API key is required." else "value_error"
        return error_response(message, [code])
    logger.exception("%s failed: %s", context, exc)
    return error_response(str(exc).strip() or f"Unexpected error while running {context}.", ["unexpected_error"])

