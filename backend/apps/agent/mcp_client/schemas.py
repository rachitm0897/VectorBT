from __future__ import annotations

from typing import Any


SUPPORTED_MCP_LOOKBACKS = {"1mo", "6mo", "1y", "2y", "5y"}


def build_strategy_research_arguments(parsed_request: dict[str, Any]) -> dict[str, Any]:
    monte_carlo = parsed_request.get("monte_carlo") or {}
    if not isinstance(monte_carlo, dict):
        monte_carlo = {}

    return {
        "symbol": str(parsed_request.get("symbol") or "").strip().upper(),
        "strategy": str(parsed_request.get("strategy") or "sma_crossover"),
        "parameters": parsed_request.get("parameters") if isinstance(parsed_request.get("parameters"), dict) else {},
        "lookback": normalize_mcp_lookback(parsed_request.get("lookback")),
        "resolution": "D",
        "initial_cash": positive_float(parsed_request.get("initial_cash"), 10000.0),
        "fees": non_negative_float(parsed_request.get("fees"), 0.001),
        "run_monte_carlo": bool(monte_carlo.get("enabled", True)),
        "monte_carlo_days": bounded_int(monte_carlo.get("days"), 60, 1, 252),
        "monte_carlo_simulations": bounded_int(monte_carlo.get("simulations"), 500, 10, 5000),
    }


def normalize_mcp_lookback(value: Any) -> str:
    lookback = str(value or "2y").strip().lower()
    aliases = {
        "1m": "1mo",
        "1mo": "1mo",
        "1month": "1mo",
        "1_month": "1mo",
        "6m": "6mo",
        "6mo": "6mo",
        "6month": "6mo",
        "6_month": "6mo",
        "1yr": "1y",
        "1year": "1y",
        "1_year": "1y",
        "2yr": "2y",
        "2year": "2y",
        "2_year": "2y",
        "5yr": "5y",
        "5year": "5y",
        "5_year": "5y",
    }
    lookback = aliases.get(lookback, lookback)
    return lookback if lookback in SUPPORTED_MCP_LOOKBACKS else "2y"


def bounded_int(value: Any, default: int, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, lower), upper)


def positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def non_negative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default
