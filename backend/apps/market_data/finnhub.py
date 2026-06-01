import hashlib
import json
from pathlib import Path

import pandas as pd
import requests
from django.conf import settings


class MarketDataError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def fetch_daily_ohlcv(symbol: str, resolution: str, start_ts: int, end_ts: int) -> pd.DataFrame:
    if resolution != "D":
        raise MarketDataError("invalid_resolution", "Only daily Finnhub candles are supported.")

    payload = _load_or_fetch_payload(symbol, resolution, start_ts, end_ts)
    return _payload_to_dataframe(payload)


def _load_or_fetch_payload(symbol: str, resolution: str, start_ts: int, end_ts: int) -> dict:
    cache_path = _cache_path(symbol, resolution, start_ts, end_ts)
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    api_key = settings.FINNHUB_API_KEY
    if not api_key:
        raise MarketDataError(
            "missing_finnhub_api_key",
            "FINNHUB_API_KEY is required when no cached market data is available.",
        )

    response = requests.get(
        "https://finnhub.io/api/v1/stock/candle",
        params={
            "symbol": symbol,
            "resolution": resolution,
            "from": start_ts,
            "to": end_ts,
            "token": api_key,
        },
        timeout=20,
    )

    if response.status_code != 200:
        raise MarketDataError(
            "finnhub_http_error",
            f"Finnhub returned HTTP {response.status_code}.",
        )

    payload = response.json()
    _validate_payload_has_data(payload)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    return payload


def _payload_to_dataframe(payload: dict) -> pd.DataFrame:
    _validate_payload_has_data(payload)

    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(payload["t"], unit="s", utc=True).tz_convert(None),
            "open": payload["o"],
            "high": payload["h"],
            "low": payload["l"],
            "close": payload["c"],
            "volume": payload["v"],
        }
    )

    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = (
        frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
        .drop_duplicates(subset=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )

    if frame.empty:
        raise MarketDataError(
            "no_data",
            "Finnhub returned no candles for this symbol and date range.",
        )

    return frame


def _validate_payload_has_data(payload: dict) -> None:
    if payload.get("s") != "ok":
        raise MarketDataError(
            "no_data",
            "Finnhub returned no candles for this symbol and date range.",
        )

    required = ["t", "o", "h", "l", "c", "v"]
    if any(key not in payload or not payload[key] for key in required):
        raise MarketDataError(
            "no_data",
            "Finnhub returned no candles for this symbol and date range.",
        )


def _cache_path(symbol: str, resolution: str, start_ts: int, end_ts: int) -> Path:
    raw_key = f"{symbol}_{resolution}_{start_ts}_{end_ts}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    safe_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum() or ch in {"-", "."})
    filename = f"{safe_symbol}_{resolution}_{start_ts}_{end_ts}_{digest}.json"
    return Path(settings.MARKET_DATA_CACHE_DIR) / filename
