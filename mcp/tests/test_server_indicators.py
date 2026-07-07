import numpy as np
import pandas as pd

import server
import tools.legacy as legacy_tools


def synthetic_market_data(periods: int = 90):
    x = np.arange(periods, dtype=float)
    close = 100 + (x * 0.15) + np.sin(x / 5)
    df = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=periods, freq="D").strftime(
                "%Y-%m-%d"
            ),
            "open": close - 0.25,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 10_000 + (x * 100),
        }
    )
    metadata = {
        "symbol": "AAPL",
        "resolution": "D",
        "lookback": "2y",
        "candles_fetched": len(df),
        "start_date": df["time"].iloc[0],
        "end_date": df["time"].iloc[-1],
        "cache_status": "HIT",
    }
    return df, metadata


def test_list_indicators_and_get_indicator_info():
    listed = server.list_indicators()
    assert listed["status"] == "success"
    assert {"RSI", "SMA", "BBANDS"}.issubset(listed["indicators"])

    info = server.get_indicator_info("rsi")
    assert info["status"] == "success"
    assert info["indicator"] == "RSI"
    assert info["info"]["name"] == "RSI"


def test_compute_indicator_serializes_outputs(monkeypatch):
    df, metadata = synthetic_market_data()
    monkeypatch.setattr(legacy_tools, "fetch_finnhub_candles_with_metadata", lambda *args, **kwargs: (df, metadata))

    response = server.compute_indicator(
        "AAPL",
        "SMA",
        {"timeperiod": 10},
        finnhub_api_key="test-key",
    )

    assert response["status"] == "success"
    assert response["indicator"] == "SMA"
    assert set(response["outputs"]) == {"real"}
    assert response["outputs"]["real"][0]["value"] is None
    assert response["outputs"]["real"][-1]["value"] is not None


def test_compute_indicators_batch_fetches_once_and_reports_partial_failures(monkeypatch):
    df, metadata = synthetic_market_data()
    calls = 0

    def fake_fetch(*args, **kwargs):
        nonlocal calls
        calls += 1
        return df, metadata

    monkeypatch.setattr(legacy_tools, "fetch_finnhub_candles_with_metadata", fake_fetch)

    response = server.compute_indicators_batch(
        "AAPL",
        [
            {"name": "SMA", "parameters": {"timeperiod": 10}, "alias": "trend"},
            {"name": "not_real", "parameters": {}},
            {"name": "BBANDS", "parameters": {"timeperiod": 20}},
        ],
        finnhub_api_key="test-key",
    )

    assert calls == 1
    assert response["status"] == "partial_success"
    assert [item["indicator"] for item in response["indicators"]] == ["SMA", "BBANDS"]
    assert response["indicators"][0]["alias"] == "trend"
    assert response["indicator_errors"][0]["indicator"] == "NOT_REAL"
