import pytest
import pandas as pd

from tools.strategies import STRATEGY_REGISTRY, generate_strategy_signals


def synthetic_prices():
    closes = [
        100,
        101,
        102,
        103,
        104,
        105,
        104,
        103,
        102,
        101,
        100,
        99,
        98,
        99,
        100,
        101,
        102,
        103,
        104,
        105,
        106,
        107,
        108,
        107,
        106,
        105,
        104,
        103,
        102,
        101,
    ]
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=len(closes), freq="D").strftime(
                "%Y-%m-%d"
            ),
            "close": closes,
        }
    )


def assert_signal_shape(signals, expected_length):
    assert set(signals) == {"entries", "exits", "parameters", "indicators"}
    assert len(signals["entries"]) == expected_length
    assert len(signals["exits"]) == expected_length
    assert signals["entries"].dtype == bool
    assert signals["exits"].dtype == bool
    assert isinstance(signals["parameters"], dict)
    assert isinstance(signals["indicators"], dict)
    assert all(isinstance(values, pd.Series) for values in signals["indicators"].values())


def test_sma_strategy_returns_entries_and_exits():
    df = synthetic_prices()
    signals = generate_strategy_signals(
        df,
        "sma_crossover",
        {"fast_window": 3, "slow_window": 5},
    )
    assert_signal_shape(signals, len(df))


def test_rsi_strategy_returns_entries_and_exits():
    df = synthetic_prices()
    signals = generate_strategy_signals(
        df,
        "rsi_mean_reversion",
        {"rsi_window": 5, "lower": 35, "upper": 65},
    )
    assert_signal_shape(signals, len(df))


def test_bollinger_strategy_returns_entries_and_exits():
    df = synthetic_prices()
    signals = generate_strategy_signals(
        df,
        "bollinger_reversion",
        {"window": 5, "std_dev": 1.5},
    )
    assert_signal_shape(signals, len(df))


def test_macd_strategy_returns_crossover_signals_and_indicators():
    df = synthetic_prices()
    signals = generate_strategy_signals(
        df,
        "macd_crossover",
        {"fast_period": 3, "slow_period": 6, "signal_period": 2},
    )
    assert_signal_shape(signals, len(df))
    assert set(signals["indicators"]) == {"macd", "signal", "histogram"}
    assert signals["entries"].any()
    assert signals["exits"].any()


def test_invalid_parameters_are_rejected():
    df = synthetic_prices()
    with pytest.raises(ValueError):
        generate_strategy_signals(
            df,
            "sma_crossover",
            {"fast_window": 20, "slow_window": 5},
        )


def test_existing_strategy_names_are_registered():
    assert set(STRATEGY_REGISTRY) == {
        "sma_crossover",
        "rsi_mean_reversion",
        "bollinger_reversion",
        "macd_crossover",
    }


def test_invalid_strategy_name_is_rejected():
    with pytest.raises(ValueError, match="Unsupported strategy 'not_real'"):
        generate_strategy_signals(synthetic_prices(), "not_real")
