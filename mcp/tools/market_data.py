from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from tools.cache import cache_dir, cache_key, read_json, write_json


FINNHUB_CANDLES_URL = "https://finnhub.io/api/v1/stock/candle"
FINNHUB_PROFILE_URL = "https://finnhub.io/api/v1/stock/profile2"
FINNHUB_METRIC_URL = "https://finnhub.io/api/v1/stock/metric"
FINNHUB_RECOMMENDATION_URL = "https://finnhub.io/api/v1/stock/recommendation"
FINNHUB_EARNINGS_URL = "https://finnhub.io/api/v1/stock/earnings"
SUPPORTED_LOOKBACKS = {
    "1mo": 31,
    "6mo": 183,
    "1y": 365,
    "2y": 365 * 2,
    "5y": 365 * 5,
}
COMPANY_TO_SYMBOL = {
    "apple": "AAPL",
    "tesla": "TSLA",
    "nvidia": "NVDA",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "netflix": "NFLX",
}


def normalize_symbol(symbol: str) -> str:
    cleaned = " ".join(symbol.strip().split())
    if not cleaned:
        raise ValueError("Symbol is required.")
    mapped = COMPANY_TO_SYMBOL.get(cleaned.lower())
    if mapped:
        return mapped
    return cleaned.upper()


def _timestamp_range(lookback: str) -> tuple[int, int]:
    if lookback not in SUPPORTED_LOOKBACKS:
        allowed = ", ".join(SUPPORTED_LOOKBACKS)
        raise ValueError(f"Unsupported lookback '{lookback}'. Allowed values: {allowed}.")
    today = datetime.now(timezone.utc).date()
    end = datetime.combine(today, time(23, 59, 59), tzinfo=timezone.utc)
    start = end - timedelta(days=SUPPORTED_LOOKBACKS[lookback])
    return int(start.timestamp()), int(end.timestamp())


def _cache_path(symbol: str, resolution: str, start_ts: int, end_ts: int):
    key = cache_key(symbol, resolution, start_ts, end_ts)
    return cache_dir("market_data") / f"{symbol}_{resolution}_{start_ts}_{end_ts}_{key}.json"


def _provider_cache_path(provider: str, symbol: str, *parts: Any):
    key = cache_key(provider, symbol, *parts)
    return cache_dir("fundamentals") / f"{provider}_{symbol}_{key}.json"


def _payload_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    if payload.get("s") != "ok":
        status = payload.get("s", "unknown")
        raise ValueError(f"Finnhub returned no candle data. Status: {status}.")

    required = ["t", "o", "h", "l", "c", "v"]
    if any(key not in payload for key in required):
        raise ValueError("Finnhub response is missing required OHLCV fields.")

    df = pd.DataFrame(
        {
            "time": pd.to_datetime(payload["t"], unit="s", utc=True),
            "open": payload["o"],
            "high": payload["h"],
            "low": payload["l"],
            "close": payload["c"],
            "volume": payload["v"],
        }
    )
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["time", *numeric_columns])
    df = df[df["close"] > 0]
    df = df.sort_values("time").drop_duplicates(subset=["time"], keep="last")
    df = df.reset_index(drop=True)
    df["time"] = df["time"].dt.strftime("%Y-%m-%d")

    if df.empty:
        raise ValueError("No valid OHLCV candles were returned.")

    return df


def _metadata(symbol: str, resolution: str, lookback: str, df: pd.DataFrame, cache_status: str):
    return {
        "symbol": symbol,
        "resolution": resolution,
        "lookback": lookback,
        "candles_fetched": int(len(df)),
        "start_date": str(df["time"].iloc[0]),
        "end_date": str(df["time"].iloc[-1]),
        "cache_status": cache_status,
    }


def fetch_finnhub_candles_with_metadata(
    symbol: str,
    lookback: str = "2y",
    resolution: str = "D",
    api_key: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized_symbol = normalize_symbol(symbol)
    if resolution != "D":
        raise ValueError("Only daily resolution 'D' is supported by this prototype.")

    api_key = (api_key or os.getenv("FINNHUB_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("Finnhub API key is required.")

    start_ts, end_ts = _timestamp_range(lookback)
    path = _cache_path(normalized_symbol, resolution, start_ts, end_ts)
    cached = read_json(path)
    if cached:
        df = _payload_to_frame(cached["payload"])
        return df, _metadata(normalized_symbol, resolution, lookback, df, "HIT")

    try:
        response = requests.get(
            FINNHUB_CANDLES_URL,
            params={
                "symbol": normalized_symbol,
                "resolution": resolution,
                "from": start_ts,
                "to": end_ts,
                "token": api_key,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ValueError("Finnhub request failed due to a network or connection error.") from exc
    if response.status_code >= 400:
        raise ValueError(f"Finnhub request failed with HTTP {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Finnhub returned a response that was not valid JSON.") from exc
    df = _payload_to_frame(payload)
    write_json(
        path,
        {
            "symbol": normalized_symbol,
            "resolution": resolution,
            "lookback": lookback,
            "from": start_ts,
            "to": end_ts,
            "payload": payload,
        },
    )
    return df, _metadata(normalized_symbol, resolution, lookback, df, "MISS")


def fetch_finnhub_candles(
    symbol: str,
    lookback: str = "2y",
    resolution: str = "D",
    api_key: str | None = None,
) -> pd.DataFrame:
    df, _ = fetch_finnhub_candles_with_metadata(
        symbol,
        lookback=lookback,
        resolution=resolution,
        api_key=api_key,
    )
    return df


def fetch_finnhub_company_profile(symbol: str, api_key: str | None = None) -> dict[str, Any]:
    return _fetch_finnhub_json(
        "profile",
        FINNHUB_PROFILE_URL,
        normalize_symbol(symbol),
        {"symbol": normalize_symbol(symbol)},
        api_key=api_key,
    )


def fetch_finnhub_basic_financials(symbol: str, api_key: str | None = None) -> dict[str, Any]:
    return _fetch_finnhub_json(
        "metrics",
        FINNHUB_METRIC_URL,
        normalize_symbol(symbol),
        {"symbol": normalize_symbol(symbol), "metric": "all"},
        api_key=api_key,
    )


def fetch_finnhub_recommendations(symbol: str, api_key: str | None = None) -> list[dict[str, Any]]:
    payload = _fetch_finnhub_json(
        "recommendations",
        FINNHUB_RECOMMENDATION_URL,
        normalize_symbol(symbol),
        {"symbol": normalize_symbol(symbol)},
        api_key=api_key,
    )
    return payload if isinstance(payload, list) else []


def fetch_finnhub_earnings(symbol: str, api_key: str | None = None) -> list[dict[str, Any]]:
    payload = _fetch_finnhub_json(
        "earnings",
        FINNHUB_EARNINGS_URL,
        normalize_symbol(symbol),
        {"symbol": normalize_symbol(symbol)},
        api_key=api_key,
    )
    return payload if isinstance(payload, list) else []


def fetch_finnhub_factor_data(symbol: str, api_key: str | None = None) -> dict[str, Any]:
    warnings: list[str] = []
    data: dict[str, Any] = {}
    for key, fetcher in (
        ("profile", fetch_finnhub_company_profile),
        ("metrics", fetch_finnhub_basic_financials),
        ("recommendations", fetch_finnhub_recommendations),
        ("earnings", fetch_finnhub_earnings),
    ):
        try:
            data[key] = fetcher(symbol, api_key=api_key)
        except ValueError as exc:
            warnings.append(f"{key}_unavailable:{exc}")
            data[key] = [] if key in {"recommendations", "earnings"} else {}
    data["warnings"] = warnings
    return data


def _fetch_finnhub_json(
    provider: str,
    url: str,
    symbol: str,
    params: dict[str, Any],
    api_key: str | None = None,
) -> Any:
    api_key = (api_key or os.getenv("FINNHUB_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("Finnhub API key is required.")

    path = _provider_cache_path(provider, symbol, *sorted(params.items()))
    cached = read_json(path)
    if cached and "payload" in cached:
        return cached["payload"]

    try:
        response = requests.get(url, params={**params, "token": api_key}, timeout=30)
    except requests.RequestException as exc:
        raise ValueError("Finnhub request failed due to a network or connection error.") from exc
    if response.status_code >= 400:
        raise ValueError(f"Finnhub request failed with HTTP {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Finnhub returned a response that was not valid JSON.") from exc
    write_json(path, {"provider": provider, "symbol": symbol, "params": params, "payload": payload})
    return payload
