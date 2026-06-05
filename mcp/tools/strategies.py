from __future__ import annotations

from typing import Any

import pandas as pd

from tools.talib_adapter import compute_talib_indicator


def list_strategy_definitions() -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "display_name": definition["display_name"],
            "description": definition["description"],
        }
        for name, definition in STRATEGY_REGISTRY.items()
    ]


def strategy_schema(strategy: str) -> dict[str, dict[str, float | int | str]]:
    if strategy not in STRATEGY_REGISTRY:
        raise ValueError(f"Unsupported strategy '{strategy}'.")
    return {
        name: dict(schema)
        for name, schema in STRATEGY_REGISTRY[strategy]["schema"].items()
    }


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
    if strategy == "macd_crossover" and cleaned["fast_period"] >= cleaned["slow_period"]:
        raise ValueError("Parameter 'fast_period' must be less than 'slow_period'.")
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


def _talib_strategy_frame(df: pd.DataFrame) -> pd.DataFrame:
    close = _close_series(df)
    frame = df.copy()
    for column in ("open", "high", "low"):
        if column not in frame.columns:
            frame[column] = frame["close"]
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    if "time" not in frame.columns:
        frame.index = close.index
    return frame


def sma_crossover(df: pd.DataFrame, parameters: dict[str, Any] | None = None):
    params = validate_strategy_parameters("sma_crossover", parameters)
    close = _close_series(df)
    talib_frame = _talib_strategy_frame(df)
    fast_sma = compute_talib_indicator(
        talib_frame,
        "SMA",
        {"timeperiod": int(params["fast_window"])},
    )["real"].rename("fast_sma")
    slow_sma = compute_talib_indicator(
        talib_frame,
        "SMA",
        {"timeperiod": int(params["slow_window"])},
    )["real"].rename("slow_sma")
    fast_sma = fast_sma.reindex(close.index)
    slow_sma = slow_sma.reindex(close.index)
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


def rsi_mean_reversion(df: pd.DataFrame, parameters: dict[str, Any] | None = None):
    params = validate_strategy_parameters("rsi_mean_reversion", parameters)
    close = _close_series(df)
    rsi = compute_talib_indicator(
        _talib_strategy_frame(df),
        "RSI",
        {"timeperiod": int(params["rsi_window"])},
    )["real"].rename("rsi")
    rsi = rsi.reindex(close.index)
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
    bands = compute_talib_indicator(
        _talib_strategy_frame(df),
        "BBANDS",
        {
            "timeperiod": int(params["window"]),
            "nbdevup": float(params["std_dev"]),
            "nbdevdn": float(params["std_dev"]),
        },
    )
    upper = bands["upperband"].rename("upper_band").reindex(close.index)
    middle = bands["middleband"].rename("middle_band").reindex(close.index)
    lower = bands["lowerband"].rename("lower_band").reindex(close.index)
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


def macd_crossover(df: pd.DataFrame, parameters: dict[str, Any] | None = None):
    params = validate_strategy_parameters("macd_crossover", parameters)
    close = _close_series(df)
    outputs = compute_talib_indicator(
        _talib_strategy_frame(df),
        "MACD",
        {
            "fastperiod": int(params["fast_period"]),
            "slowperiod": int(params["slow_period"]),
            "signalperiod": int(params["signal_period"]),
        },
    )
    macd = outputs["macd"].rename("macd").reindex(close.index)
    signal = outputs["macdsignal"].rename("signal").reindex(close.index)
    histogram = outputs["macdhist"].rename("histogram").reindex(close.index)
    above = (macd > signal).fillna(False).astype(bool)
    previous_above = above.shift(1, fill_value=False).astype(bool)
    entries = _bool_series(above & ~previous_above, close.index)
    exits = _bool_series(~above & previous_above, close.index)
    return {
        "entries": entries,
        "exits": exits,
        "parameters": params,
        "indicators": {
            "macd": macd,
            "signal": signal,
            "histogram": histogram,
        },
    }


STRATEGY_REGISTRY: dict[str, dict[str, Any]] = {
    "sma_crossover": {
        "display_name": "SMA Crossover",
        "description": "Long-only moving average crossover strategy.",
        "schema": {
            "fast_window": {"type": "integer", "default": 20, "min": 2, "max": 300},
            "slow_window": {"type": "integer", "default": 50, "min": 3, "max": 500},
        },
        "runner": sma_crossover,
    },
    "rsi_mean_reversion": {
        "display_name": "RSI Mean Reversion",
        "description": (
            "Buys when RSI is below lower threshold and exits when RSI is above upper threshold."
        ),
        "schema": {
            "rsi_window": {"type": "integer", "default": 14, "min": 2, "max": 100},
            "lower": {"type": "number", "default": 30, "min": 1, "max": 50},
            "upper": {"type": "number", "default": 70, "min": 50, "max": 99},
        },
        "runner": rsi_mean_reversion,
    },
    "bollinger_reversion": {
        "display_name": "Bollinger Band Reversion",
        "description": "Buys when close is below lower Bollinger Band and exits above middle band.",
        "schema": {
            "window": {"type": "integer", "default": 20, "min": 2, "max": 300},
            "std_dev": {"type": "number", "default": 2, "min": 0.5, "max": 5},
        },
        "runner": bollinger_reversion,
    },
    "macd_crossover": {
        "display_name": "MACD Crossover",
        "description": (
            "Enters when MACD crosses above its signal line and exits when it crosses below."
        ),
        "schema": {
            "fast_period": {"type": "integer", "default": 12, "min": 2, "max": 100},
            "slow_period": {"type": "integer", "default": 26, "min": 3, "max": 200},
            "signal_period": {"type": "integer", "default": 9, "min": 2, "max": 100},
        },
        "runner": macd_crossover,
    },
}


def generate_strategy_signals(
    df: pd.DataFrame,
    strategy: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = STRATEGY_REGISTRY.get(strategy)
    if definition is None:
        raise ValueError(f"Unsupported strategy '{strategy}'.")
    validated_parameters = validate_strategy_parameters(strategy, parameters)
    return definition["runner"](df, validated_parameters)
