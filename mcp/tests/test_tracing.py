import sys

import pandas as pd
import pytest

from tools.tracing import (
    REDACTED,
    is_langsmith_enabled,
    safe_metadata,
    summarize_output,
    traced_tool,
)


def test_tracing_disabled_keeps_tool_behavior(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    @traced_tool()
    def add(left, right=2):
        return left + right

    assert is_langsmith_enabled() is False
    assert add(3) == 5


def test_secret_redaction_covers_finnhub_and_openai_keys():
    sanitized = safe_metadata(
        {
            "finnhub_api_key": "finnhub-secret",
            "openai_api_key": "sk-super-secret-value",
            "nested": {
                "authorization": "Bearer hidden-token",
                "symbol": "AAPL",
            },
        }
    )

    assert sanitized["finnhub_api_key"] == REDACTED
    assert sanitized["openai_api_key"] == REDACTED
    assert sanitized["nested"]["authorization"] == REDACTED
    assert sanitized["nested"]["symbol"] == "AAPL"
    assert "finnhub-secret" not in str(sanitized)
    assert "sk-super-secret-value" not in str(sanitized)


def test_traced_tool_preserves_return_values_and_exceptions(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    @traced_tool()
    def identity(value):
        return value

    @traced_tool()
    def fail():
        raise ValueError("expected failure")

    payload = {"status": "success", "symbol": "AAPL"}
    assert identity(payload) is payload
    with pytest.raises(ValueError, match="expected failure"):
        fail()


def test_trace_setup_failure_is_non_blocking(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only-key")
    monkeypatch.setitem(sys.modules, "langsmith", None)

    @traced_tool()
    def tool():
        return {"status": "success"}

    assert tool() == {"status": "success"}


def test_large_dataframe_and_indicator_outputs_are_summarized():
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=100, freq="D"),
            "close": range(100),
        }
    )
    frame_summary = summarize_output(frame)
    indicator_summary = summarize_output(
        {
            "status": "success",
            "indicator": "RSI",
            "outputs": {
                "real": [{"time": str(index), "value": index} for index in range(1000)]
            },
        }
    )

    assert frame_summary["rows"] == 100
    assert frame_summary["columns"] == ["time", "close"]
    assert indicator_summary["outputs"]["fields"] == ["real"]
    assert indicator_summary["outputs"]["points"]["real"] == 1000
    assert len(str(indicator_summary)) < 500
