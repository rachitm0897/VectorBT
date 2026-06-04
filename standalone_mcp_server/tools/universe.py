from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from tools.cache import SERVER_ROOT


UNIVERSE_FILENAME = "us_stocks_only_universe.json"


def get_universe_path() -> Path:
    configured = (
        os.getenv("US_STOCK_UNIVERSE_PATH")
        or os.getenv("MCP_US_STOCK_UNIVERSE_PATH")
        or ""
    ).strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = SERVER_ROOT / path
        if path.exists():
            return path.resolve()

    candidates = [
        SERVER_ROOT.parent / UNIVERSE_FILENAME,
        SERVER_ROOT / UNIVERSE_FILENAME,
        Path.cwd() / UNIVERSE_FILENAME,
    ]
    for path in candidates:
        if path.exists():
            return path.resolve()

    search_root = SERVER_ROOT.parent
    matches = sorted(search_root.rglob(UNIVERSE_FILENAME))
    if matches:
        return matches[0].resolve()

    raise FileNotFoundError(f"{UNIVERSE_FILENAME} was not found.")


@lru_cache(maxsize=1)
def load_us_stock_universe() -> list[dict[str, Any]]:
    path = get_universe_path()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [normalize_universe_item(item) for item in _extract_items(payload)]


def normalize_universe_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    ticker = _clean_symbol(
        item.get("ticker")
        or item.get("symbol")
        or item.get("exchange_symbol")
        or item.get("yfinance_symbol")
    )
    return {
        "ticker": ticker,
        "symbol": _clean_symbol(item.get("symbol") or ticker),
        "exchange_symbol": _clean_symbol(item.get("exchange_symbol") or ticker),
        "finnhub_symbol": _clean_text(item.get("finnhub_symbol")),
        "backtest_ticker": _clean_text(item.get("backtest_ticker")),
        "yfinance_symbol": _clean_symbol(item.get("yfinance_symbol") or ticker),
        "name": _clean_text(item.get("name")),
        "exchange": _clean_text(item.get("exchange")),
        "country": _clean_text(item.get("country") or "US"),
        "currency": _clean_text(item.get("currency") or "USD"),
        "sector": _clean_text(metadata.get("Sector") or "Unclassified"),
        "market_cap": _clean_text(metadata.get("Market Cap")),
        "approx_price": _clean_text(metadata.get("Approx Price")),
        "strategy_fit": _clean_text(metadata.get("Strategy Fit")),
        "options_available": _clean_text(metadata.get("Options Avail?")),
        "iv_profile": _clean_text(metadata.get("IV Profile")),
        "risk_level": _clean_text(metadata.get("Risk Level")),
        "notes": _clean_text(metadata.get("Notes")),
    }


def list_sectors() -> list[str]:
    sectors = {
        item["sector"]
        for item in load_us_stock_universe()
        if item.get("sector") and item.get("sector") != "Unclassified"
    }
    return sorted(sectors)


def list_all_stocks() -> list[dict[str, Any]]:
    return sorted(
        (_compact_stock(item) for item in load_us_stock_universe()),
        key=lambda item: item["ticker"],
    )


def list_stocks_by_sector(sector: str) -> list[dict[str, Any]]:
    wanted = _normalize_lookup_key(sector)
    stocks = [
        item
        for item in load_us_stock_universe()
        if _normalize_lookup_key(item.get("sector")) == wanted
    ]
    return sorted((_compact_stock(item) for item in stocks), key=lambda item: item["ticker"])


def resolve_symbols_for_sector(sector: str) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for stock in list_stocks_by_sector(sector):
        symbol = _clean_symbol(
            stock.get("ticker")
            or stock.get("backtest_ticker")
            or stock.get("finnhub_symbol")
        )
        if symbol and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    return symbols


def get_stock_by_ticker(ticker: str) -> dict[str, Any] | None:
    lookup = _symbol_lookup()
    item = lookup.get(_normalize_lookup_key(ticker))
    return dict(item) if item else None


def validate_symbols(symbols: list[str]) -> list[str]:
    lookup = _symbol_lookup()
    valid: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        item = lookup.get(_normalize_lookup_key(symbol))
        if not item:
            continue
        ticker = str(item.get("ticker") or "").upper()
        if ticker and ticker not in seen:
            valid.append(ticker)
            seen.add(ticker)
    return valid


def resolve_market_data_symbol(ticker: str) -> str:
    item = get_stock_by_ticker(ticker)
    if not item:
        return _clean_symbol(ticker)

    # tools.market_data.fetch_finnhub_candles_with_metadata expects ordinary
    # ticker symbols such as AAPL rather than exchange-prefixed symbols.
    return _clean_symbol(item.get("ticker") or item.get("symbol") or ticker)


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        raise ValueError("Stock universe JSON must be an object or list.")

    for key in ("tickers", "stocks", "items", "universe", "data"):
        value = payload.get(key)
        if isinstance(value, list) and any(isinstance(item, dict) for item in value):
            return [item for item in value if isinstance(item, dict)]

    symbols = payload.get("symbols")
    if isinstance(symbols, list):
        return [{"ticker": symbol, "symbol": symbol} for symbol in symbols if isinstance(symbol, str)]

    raise ValueError("Stock universe JSON does not include detailed stock records.")


def _compact_stock(item: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "ticker",
        "name",
        "sector",
        "exchange",
        "currency",
        "market_cap",
        "risk_level",
        "iv_profile",
        "strategy_fit",
        "notes",
    ]
    return {key: item.get(key) for key in keys}


@lru_cache(maxsize=1)
def _symbol_lookup() -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in load_us_stock_universe():
        for key in (
            "ticker",
            "symbol",
            "exchange_symbol",
            "finnhub_symbol",
            "backtest_ticker",
            "yfinance_symbol",
        ):
            value = item.get(key)
            if value:
                lookup[_normalize_lookup_key(value)] = item

        ticker = item.get("ticker")
        if ticker:
            lookup[_normalize_lookup_key(str(ticker).split(":")[-1])] = item
    return lookup


def _normalize_lookup_key(value: Any) -> str:
    text = str(value or "").strip().upper()
    if ":" in text:
        text = text.split(":")[-1]
    return text


def _clean_symbol(value: Any) -> str:
    return _normalize_lookup_key(value)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
