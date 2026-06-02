from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


STRATEGIES = [
    {
        "name": "sma_crossover",
        "display_name": "SMA Crossover",
        "description": "Long-only moving average crossover strategy.",
    },
    {
        "name": "rsi_mean_reversion",
        "display_name": "RSI Mean Reversion",
        "description": "Buys when RSI is below lower threshold and exits when RSI is above upper threshold.",
    },
    {
        "name": "bollinger_reversion",
        "display_name": "Bollinger Band Reversion",
        "description": "Buys when close is below lower Bollinger Band and exits above middle band.",
    },
]

STRATEGY_SCHEMAS: dict[str, dict[str, dict[str, float | int | str]]] = {
    "sma_crossover": {
        "fast_window": {"type": "integer", "default": 20, "min": 2, "max": 300},
        "slow_window": {"type": "integer", "default": 50, "min": 3, "max": 500},
    },
    "rsi_mean_reversion": {
        "rsi_window": {"type": "integer", "default": 14, "min": 2, "max": 100},
        "lower": {"type": "number", "default": 30, "min": 1, "max": 50},
        "upper": {"type": "number", "default": 70, "min": 50, "max": 99},
    },
    "bollinger_reversion": {
        "window": {"type": "integer", "default": 20, "min": 2, "max": 300},
        "std_dev": {"type": "number", "default": 2, "min": 0.5, "max": 5},
    },
}


def list_strategy_definitions() -> list[dict[str, str]]:
    return [dict(item) for item in STRATEGIES]


def strategy_schema(strategy: str) -> dict[str, dict[str, float | int | str]]:
    if strategy not in STRATEGY_SCHEMAS:
        raise ValueError(f"Unsupported strategy '{strategy}'.")
    return {name: dict(schema) for name, schema in STRATEGY_SCHEMAS[strategy].items()}


def _parameter_defaults(strategy: str) -> dict[str, Any]:
    return {name: schema["default"] for name, schema in strategy_schema(strategy).items()}


def _validate_number(name: str, value: Any, schema: dict[str, Any]) -> float | int:
    expected_type = schema["type"]
    if expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Parameter '{name}' must be an integer.")
        cleaned: float | int = value
    else:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Parameter '{name}' must be a number.")
        cleaned = float(value)

    if cleaned < schema["min"] or cleaned > schema["max"]:
        raise ValueError(
            f"Parameter '{name}' must be between {schema['min']} and {schema['max']}."
        )
    return cleaned


def validate_strategy_parameters(strategy: str, parameters: dict[str, Any] | None = None):
    schema = strategy_schema(strategy)
    merged = _parameter_defaults(strategy)
    merged.update(parameters or {})

    unknown = sorted(set(merged) - set(schema))
    if unknown:
        raise ValueError(f"Unsupported parameter(s) for {strategy}: {', '.join(unknown)}.")

    cleaned = {name: _validate_number(name, merged[name], schema[name]) for name in schema}
    if strategy == "sma_crossover" and cleaned["fast_window"] >= cleaned["slow_window"]:
        raise ValueError("Parameter 'fast_window' must be less than 'slow_window'.")
    if strategy == "rsi_mean_reversion" and cleaned["lower"] >= cleaned["upper"]:
        raise ValueError("Parameter 'lower' must be less than 'upper'.")
    return cleaned


def _close_series(df: pd.DataFrame) -> pd.Series:
    if "close" not in df.columns:
        raise ValueError("Input data must include a 'close' column.")
    close = pd.to_numeric(df["close"], errors="coerce")
    if close.dropna().empty:
        raise ValueError("Input data does not contain valid close prices.")
    if "time" in df.columns:
        close.index = pd.Index(df["time"].astype(str), name="time")
    return close


def _bool_series(values: pd.Series, index: pd.Index) -> pd.Series:
    return values.reindex(index).fillna(False).astype(bool)


def sma_crossover(df: pd.DataFrame, parameters: dict[str, Any] | None = None):
    params = validate_strategy_parameters("sma_crossover", parameters)
    close = _close_series(df)
    fast_sma = close.rolling(int(params["fast_window"]), min_periods=int(params["fast_window"])).mean()
    slow_sma = close.rolling(int(params["slow_window"]), min_periods=int(params["slow_window"])).mean()
    above = (fast_sma > slow_sma).fillna(False).astype(bool)
    previous_above = above.shift(1, fill_value=False).astype(bool)
    entries = _bool_series(above & ~previous_above, close.index)
    exits = _bool_series(~above & previous_above, close.index)
    return {
        "entries": entries,
        "exits": exits,
        "parameters": params,
        "indicators": {
            "fast_sma": fast_sma,
            "slow_sma": slow_sma,
        },
    }


def _calculate_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window, min_periods=window).mean()
    avg_loss = losses.rolling(window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50)
    return rsi


def rsi_mean_reversion(df: pd.DataFrame, parameters: dict[str, Any] | None = None):
    params = validate_strategy_parameters("rsi_mean_reversion", parameters)
    close = _close_series(df)
    rsi = _calculate_rsi(close, int(params["rsi_window"]))
    entries = _bool_series(rsi < float(params["lower"]), close.index)
    exits = _bool_series(rsi > float(params["upper"]), close.index)
    return {
        "entries": entries,
        "exits": exits,
        "parameters": params,
        "indicators": {
            "rsi": rsi,
        },
    }


def bollinger_reversion(df: pd.DataFrame, parameters: dict[str, Any] | None = None):
    params = validate_strategy_parameters("bollinger_reversion", parameters)
    close = _close_series(df)
    window = int(params["window"])
    std_dev = float(params["std_dev"])
    middle = close.rolling(window, min_periods=window).mean()
    rolling_std = close.rolling(window, min_periods=window).std()
    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std
    entries = _bool_series(close < lower, close.index)
    exits = _bool_series(close > middle, close.index)
    return {
        "entries": entries,
        "exits": exits,
        "parameters": params,
        "indicators": {
            "middle_band": middle,
            "upper_band": upper,
            "lower_band": lower,
        },
    }


def generate_strategy_signals(
    df: pd.DataFrame,
    strategy: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if strategy == "sma_crossover":
        return sma_crossover(df, parameters)
    if strategy == "rsi_mean_reversion":
        return rsi_mean_reversion(df, parameters)
    if strategy == "bollinger_reversion":
        return bollinger_reversion(df, parameters)
    raise ValueError(f"Unsupported strategy '{strategy}'.")
