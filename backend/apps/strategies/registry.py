from dataclasses import dataclass

import pandas as pd


SUPPORTED_STRATEGIES = {
    "sma_crossover",
    "rsi_mean_reversion",
    "bollinger_reversion",
}


class StrategyValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class StrategySignals:
    parameters: dict
    entries: pd.Series
    exits: pd.Series
    indicators: dict
    warnings: list[str]


def build_strategy_signals(strategy: str, close: pd.Series, parameters: dict | None) -> StrategySignals:
    if strategy not in SUPPORTED_STRATEGIES:
        raise StrategyValidationError("unsupported_strategy", f"Unsupported strategy: {strategy}.")

    parameters = parameters or {}

    if strategy == "sma_crossover":
        return _sma_crossover(close, parameters)
    if strategy == "rsi_mean_reversion":
        return _rsi_mean_reversion(close, parameters)
    if strategy == "bollinger_reversion":
        return _bollinger_reversion(close, parameters)

    raise StrategyValidationError("unsupported_strategy", f"Unsupported strategy: {strategy}.")


def _sma_crossover(close: pd.Series, raw_parameters: dict) -> StrategySignals:
    fast_window = _positive_int(raw_parameters, "fast_window", 20)
    slow_window = _positive_int(raw_parameters, "slow_window", 50)
    if fast_window >= slow_window:
        raise StrategyValidationError(
            "invalid_parameters",
            "fast_window must be smaller than slow_window for sma_crossover.",
        )

    fast = close.rolling(fast_window).mean()
    slow = close.rolling(slow_window).mean()
    entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
    exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))

    return StrategySignals(
        parameters={"fast_window": fast_window, "slow_window": slow_window},
        entries=entries.fillna(False),
        exits=exits.fillna(False),
        indicators={
            "fast_sma": _series_points(fast),
            "slow_sma": _series_points(slow),
        },
        warnings=[],
    )


def _rsi_mean_reversion(close: pd.Series, raw_parameters: dict) -> StrategySignals:
    rsi_window = _positive_int(raw_parameters, "rsi_window", 14)
    lower = _float_value(raw_parameters, "lower", 30.0)
    upper = _float_value(raw_parameters, "upper", 70.0)
    if not 0 < lower < upper < 100:
        raise StrategyValidationError(
            "invalid_parameters",
            "RSI lower and upper must satisfy 0 < lower < upper < 100.",
        )

    rsi = _rsi(close, rsi_window)
    entries = rsi < lower
    exits = rsi > upper

    return StrategySignals(
        parameters={"rsi_window": rsi_window, "lower": lower, "upper": upper},
        entries=entries.fillna(False),
        exits=exits.fillna(False),
        indicators={"rsi": _series_points(rsi)},
        warnings=[],
    )


def _bollinger_reversion(close: pd.Series, raw_parameters: dict) -> StrategySignals:
    window = _positive_int(raw_parameters, "window", 20)
    std_dev = _float_value(raw_parameters, "std_dev", 2.0)
    if std_dev <= 0:
        raise StrategyValidationError("invalid_parameters", "std_dev must be greater than zero.")

    middle = close.rolling(window).mean()
    rolling_std = close.rolling(window).std(ddof=0)
    lower_band = middle - (std_dev * rolling_std)
    upper_band = middle + (std_dev * rolling_std)

    entries = close < lower_band
    exits = close > middle

    return StrategySignals(
        parameters={"window": window, "std_dev": std_dev},
        entries=entries.fillna(False),
        exits=exits.fillna(False),
        indicators={
            "middle_band": _series_points(middle),
            "lower_band": _series_points(lower_band),
            "upper_band": _series_points(upper_band),
        },
        warnings=[],
    )


def _rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = gain.rolling(window).mean()
    average_loss = loss.rolling(window).mean()
    relative_strength = average_gain / average_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + relative_strength))
    return rsi.fillna(50)


def _positive_int(parameters: dict, key: str, default: int) -> int:
    value = parameters.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise StrategyValidationError("invalid_parameters", f"{key} must be an integer.") from exc
    if parsed <= 0:
        raise StrategyValidationError("invalid_parameters", f"{key} must be greater than zero.")
    return parsed


def _float_value(parameters: dict, key: str, default: float) -> float:
    value = parameters.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise StrategyValidationError("invalid_parameters", f"{key} must be numeric.") from exc


def _series_points(series: pd.Series) -> list[dict]:
    points = []
    for timestamp, value in series.items():
        if pd.isna(value):
            continue
        points.append({"date": timestamp.date().isoformat(), "value": float(value)})
    return points
