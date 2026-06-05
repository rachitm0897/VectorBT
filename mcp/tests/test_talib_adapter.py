import numpy as np
import pandas as pd
import pytest

from tools.talib_adapter import (
    compute_talib_indicator,
    dataframe_to_talib_inputs,
    get_talib_indicator_info,
    list_talib_indicators,
)


def synthetic_ohlcv(periods: int = 120) -> pd.DataFrame:
    x = np.arange(periods, dtype=float)
    close = 100 + (x * 0.2) + np.sin(x / 4)
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=periods, freq="D"),
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000 + (x * 10),
        }
    )


def test_list_talib_indicators_includes_core_indicators():
    indicators = list_talib_indicators()
    assert indicators == sorted(indicators)
    assert {"RSI", "SMA", "BBANDS"}.issubset(indicators)


def test_get_talib_indicator_info_returns_metadata():
    info = get_talib_indicator_info("rsi")
    assert info["name"] == "RSI"
    assert info["output_names"] == ["real"]
    assert info["parameters"]["timeperiod"] == 14


def test_dataframe_to_talib_inputs_validates_and_drops_invalid_rows():
    df = synthetic_ohlcv(10)
    df["volume"] = df["volume"].astype(object)
    df.loc[3, "volume"] = "invalid"
    inputs = dataframe_to_talib_inputs(df)
    assert set(inputs) == {"open", "high", "low", "close", "volume"}
    assert all(len(values) == 9 for values in inputs.values())
    assert all(values.dtype == float for values in inputs.values())

    with pytest.raises(ValueError, match="missing required OHLCV columns"):
        dataframe_to_talib_inputs(df.drop(columns=["volume"]))


@pytest.mark.parametrize(
    ("indicator", "parameters", "expected_outputs"),
    [
        ("SMA", {"timeperiod": 10}, {"real"}),
        ("RSI", {"timeperiod": 14}, {"real"}),
        (
            "BBANDS",
            {"timeperiod": 20, "nbdevup": 2.0, "nbdevdn": 2.0},
            {"upperband", "middleband", "lowerband"},
        ),
        (
            "MACD",
            {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
            {"macd", "macdsignal", "macdhist"},
        ),
    ],
)
def test_compute_talib_indicator_returns_indexed_series(
    indicator,
    parameters,
    expected_outputs,
):
    df = synthetic_ohlcv()
    outputs = compute_talib_indicator(df, indicator, parameters)
    expected_index = pd.Index(df["time"].astype(str), name="time")

    assert set(outputs) == expected_outputs
    for output in outputs.values():
        assert isinstance(output, pd.Series)
        assert output.index.equals(expected_index)
        assert output.notna().any()


def test_compute_talib_indicator_rejects_unknown_indicator():
    with pytest.raises(ValueError, match="Unsupported TA-Lib indicator"):
        compute_talib_indicator(synthetic_ohlcv(), "not_real")
