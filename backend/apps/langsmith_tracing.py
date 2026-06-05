from __future__ import annotations

import logging
import os
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator


logger = logging.getLogger("apps.langsmith_tracing")

REDACTED = "[REDACTED]"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "cookie",
    "password",
    "secret",
    "token",
)
_REQUEST_ID: ContextVar[str | None] = ContextVar("backend_request_id", default=None)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"\b(?:sk|lsv2)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)


def is_langsmith_enabled() -> bool:
    tracing = os.getenv("LANGSMITH_TRACING", "").strip().lower() in _TRUE_VALUES
    return tracing and bool(os.getenv("LANGSMITH_API_KEY", "").strip())


def get_request_id() -> str | None:
    return _REQUEST_ID.get()


@contextmanager
def request_id_context(request_id: str | None = None) -> Iterator[str]:
    resolved = _clean_request_id(request_id) or get_request_id() or uuid.uuid4().hex
    token = _REQUEST_ID.set(resolved)
    try:
        yield resolved
    finally:
        _REQUEST_ID.reset(token)


def safe_metadata(value: Any, *, _depth: int = 0, _key: str = "") -> Any:
    if _is_sensitive_key(_key):
        return REDACTED
    if _depth >= 6:
        return _summary_label(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, dict):
        return {
            str(key): safe_metadata(item, _depth=_depth + 1, _key=str(key))
            for key, item in list(value.items())[:50]
        }
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        sanitized = [
            safe_metadata(item, _depth=_depth + 1, _key=_key)
            for item in items[:20]
        ]
        if len(items) > 20:
            sanitized.append({"omitted_items": len(items) - 20})
        return sanitized
    if _is_dataframe(value):
        return _dataframe_summary(value)
    if _is_series(value):
        return _series_summary(value)
    if hasattr(value, "model_dump"):
        try:
            return safe_metadata(value.model_dump(), _depth=_depth + 1, _key=_key)
        except Exception:
            pass
    return _sanitize_string(str(value))


def summarize_output(value: Any) -> Any:
    if _is_dataframe(value):
        return _dataframe_summary(value)
    if _is_series(value):
        return _series_summary(value)
    if not isinstance(value, dict):
        if isinstance(value, (list, tuple, set)):
            return {"count": len(value), "sample": safe_metadata(list(value)[:5])}
        return safe_metadata(value)

    summary: dict[str, Any] = {}
    for key in (
        "status",
        "assistant_message",
        "result_type",
        "symbol",
        "strategy",
        "sector",
        "objective",
        "request",
        "parsed_request",
        "metrics",
        "summary",
        "data_quality",
        "diagnostics",
        "warnings",
        "errors",
        "missing_fields",
    ):
        if key in value:
            summary[key] = safe_metadata(value[key], _key=key)
    if "backtest_result" in value:
        backtest = value.get("backtest_result") or {}
        summary["backtest_result"] = safe_metadata(
            {
                "status": backtest.get("status"),
                "request": backtest.get("request"),
                "metrics": backtest.get("metrics"),
                "summary": backtest.get("summary"),
            }
        )
    if "portfolio_result" in value:
        portfolio = value.get("portfolio_result") or {}
        summary["portfolio_result"] = safe_metadata(
            {
                "status": portfolio.get("status"),
                "objective": portfolio.get("objective"),
                "symbols": portfolio.get("symbols_used") or portfolio.get("symbols"),
                "metrics": portfolio.get("metrics"),
            }
        )
    return summary or {"keys": list(value)[:30], "field_count": len(value)}


class TraceSpan:
    def __init__(self, run: Any = None):
        self._run = run
        self._outputs: Any = None
        self._error: str | None = None
        self._finished = False

    def set_outputs(self, value: Any) -> None:
        self._outputs = summarize_output(value)

    def set_error(self, error: BaseException | str) -> None:
        if isinstance(error, BaseException):
            detail = str(error).strip()
            message = f"{type(error).__name__}: {detail}" if detail else type(error).__name__
        else:
            message = str(error).strip() or "Unknown error"
        self._error = _sanitize_string(message)

    def finish(self) -> None:
        if self._finished or self._run is None:
            return
        self._finished = True
        try:
            self._run.end(
                outputs={"summary": self._outputs} if self._outputs is not None else None,
                error=self._error,
            )
        except Exception as exc:
            logger.debug("LangSmith trace finalization failed: %s", type(exc).__name__)


@contextmanager
def trace_request(
    name: str,
    user_request: str,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> Iterator[TraceSpan]:
    with request_id_context(request_id) as resolved_request_id:
        with _trace_span(
            name=name,
            run_type="chain",
            inputs={"user_request": user_request},
            metadata={"request_id": resolved_request_id, **(metadata or {})},
            tags=["finance", "request"],
        ) as span:
            yield span


@contextmanager
def trace_tool_call(
    tool_name: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Iterator[TraceSpan]:
    with request_id_context() as request_id:
        with _trace_span(
            name=tool_name,
            run_type="tool",
            inputs=inputs,
            metadata={
                "request_id": request_id,
                "tool_name": tool_name,
                **(metadata or {}),
            },
            tags=["mcp", "finance", "tool"],
        ) as span:
            yield span


@contextmanager
def trace_llm_call(
    name: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Iterator[TraceSpan]:
    with request_id_context() as request_id:
        with _trace_span(
            name=name,
            run_type="llm",
            inputs=inputs,
            metadata={"request_id": request_id, **(metadata or {})},
            tags=["finance", "llm"],
        ) as span:
            yield span


def current_trace_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if is_langsmith_enabled():
        try:
            from langsmith.run_helpers import get_current_run_tree

            run_tree = get_current_run_tree()
            if run_tree is not None:
                headers.update(run_tree.to_headers())
        except Exception as exc:
            logger.debug("LangSmith trace header generation failed: %s", type(exc).__name__)
    request_id = get_request_id()
    if request_id:
        headers["x-request-id"] = request_id
    return headers


@contextmanager
def _trace_span(
    *,
    name: str,
    run_type: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any],
    tags: list[str],
) -> Iterator[TraceSpan]:
    if not is_langsmith_enabled():
        disabled_cm = _open_disabled_tracing_context()
        try:
            yield TraceSpan()
        finally:
            _close_context(disabled_cm)
        return

    tracing_cm = None
    trace_cm = None
    try:
        import langsmith as ls

        tracing_cm = ls.tracing_context(
            enabled=True,
            project_name=os.getenv("LANGSMITH_PROJECT") or "finance-mcp-dev",
        )
        tracing_cm.__enter__()
        trace_cm = ls.trace(
            name,
            run_type=run_type,
            inputs=safe_metadata(inputs),
            metadata=safe_metadata(metadata),
            tags=tags,
        )
        run = trace_cm.__enter__()
    except Exception as exc:
        logger.warning("LangSmith trace setup failed; continuing untraced: %s", type(exc).__name__)
        _close_context(trace_cm)
        _close_context(tracing_cm)
        disabled_cm = _open_disabled_tracing_context()
        try:
            yield TraceSpan()
        finally:
            _close_context(disabled_cm)
        return

    span = TraceSpan(run)
    try:
        yield span
    except BaseException as exc:
        span.set_error(exc)
        span.finish()
        _close_context(trace_cm)
        _close_context(tracing_cm)
        raise
    else:
        span.finish()
        _close_context(trace_cm)
        _close_context(tracing_cm)


def _close_context(context: Any) -> None:
    if context is None:
        return
    try:
        context.__exit__(None, None, None)
    except Exception as exc:
        logger.debug("LangSmith context cleanup failed: %s", type(exc).__name__)


def _open_disabled_tracing_context() -> Any:
    try:
        import langsmith as ls

        context = ls.tracing_context(enabled=False)
        context.__enter__()
        return context
    except Exception:
        return None


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _sanitize_string(value: str) -> str:
    sanitized = value
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(
            lambda match: f"{match.group(1)} {REDACTED}" if match.lastindex else REDACTED,
            sanitized,
        )
    if len(sanitized) > 1000:
        return f"{sanitized[:1000]}...[truncated {len(sanitized) - 1000} chars]"
    return sanitized


def _clean_request_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = str(value).strip()
    if len(cleaned) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", cleaned):
        return None
    return cleaned


def _summary_label(value: Any) -> str:
    try:
        size = len(value)
    except (TypeError, AttributeError):
        size = None
    label = type(value).__name__
    return f"<{label} size={size}>" if size is not None else f"<{label}>"


def _is_dataframe(value: Any) -> bool:
    return value.__class__.__module__.startswith("pandas") and value.__class__.__name__ == "DataFrame"


def _is_series(value: Any) -> bool:
    return value.__class__.__module__.startswith("pandas") and value.__class__.__name__ == "Series"


def _dataframe_summary(frame: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": "dataframe",
        "rows": int(len(frame.index)),
        "columns": [str(column) for column in list(frame.columns)[:50]],
    }
    values = None
    for column in ("time", "date", "timestamp"):
        if column in frame.columns and len(frame.index):
            values = frame[column]
            break
    if values is None and len(frame.index):
        values = frame.index
    if values is not None and len(values):
        first = values.iloc[0] if hasattr(values, "iloc") else values[0]
        last = values.iloc[-1] if hasattr(values, "iloc") else values[-1]
        summary["first_timestamp"] = _sanitize_string(str(first))
        summary["last_timestamp"] = _sanitize_string(str(last))
    return summary


def _series_summary(series: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": "series",
        "name": str(getattr(series, "name", "") or ""),
        "points": int(len(series)),
    }
    if len(series):
        summary["first_timestamp"] = _sanitize_string(str(series.index[0]))
        summary["last_timestamp"] = _sanitize_string(str(series.index[-1]))
    return summary
