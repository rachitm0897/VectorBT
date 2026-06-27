import numpy as np
import pandas as pd

from tools.monte_carlo import (
    sample_block_bootstrap_returns,
    scenario_assumptions,
    scenario_paths_from_sampled_returns,
    transform_scenario_returns,
    run_portfolio_scenario_monte_carlo,
)
from tools.portfolio_optimization import calculate_weighted_portfolio_returns


def synthetic_returns():
    return pd.Series(
        [
            -0.015,
            0.006,
            0.011,
            -0.004,
            0.018,
            -0.009,
            0.004,
            0.013,
            -0.002,
            0.007,
            -0.011,
            0.016,
        ]
    )


def test_weighted_portfolio_returns_equal_asset_returns_multiplied_by_weights():
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 110.0, 121.0],
            "BBB": [100.0, 90.0, 99.0],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
    )

    result = calculate_weighted_portfolio_returns(prices, {"AAA": 0.25, "BBB": 0.75})

    expected = pd.Series([0.1 * 0.25 + -0.1 * 0.75, 0.1 * 0.25 + 0.1 * 0.75], index=result.index)
    assert np.allclose(result.to_numpy(), expected.to_numpy())


def test_neutral_scenario_preserves_historical_bootstrap_assumptions():
    sampled = np.array([[0.01, -0.02, 0.03]])
    assumptions = scenario_assumptions("neutral", {})

    transformed = transform_scenario_returns(sampled, historical_mean=0.005, assumptions=assumptions)

    assert assumptions == {
        "drift_shift_annual": 0.0,
        "volatility_multiplier": 1.0,
        "initial_shock_pct": 0.0,
    }
    assert np.allclose(transformed, sampled)


def test_same_seed_produces_identical_output():
    kwargs = {
        "portfolio_returns": synthetic_returns(),
        "days": 12,
        "simulations": 120,
        "block_size": 3,
        "seed": 42,
        "scenarios": ["neutral", "crash"],
    }

    first = run_portfolio_scenario_monte_carlo(**kwargs)
    second = run_portfolio_scenario_monte_carlo(**kwargs)

    assert first["compact"] == second["compact"]
    assert first["artifact"] == second["artifact"]


def test_different_seed_can_produce_different_paths():
    returns = synthetic_returns()

    first = sample_block_bootstrap_returns(returns, days=12, simulations=120, block_size=3, seed=1)
    second = sample_block_bootstrap_returns(returns, days=12, simulations=120, block_size=3, seed=2)

    assert not np.allclose(first, second)


def test_same_base_sampled_paths_are_used_across_scenarios():
    returns = synthetic_returns()
    base = sample_block_bootstrap_returns(returns, days=10, simulations=100, block_size=2, seed=42)
    neutral_paths = scenario_paths_from_sampled_returns(
        base,
        start_value=10000,
        assumptions=scenario_assumptions("neutral", {}),
        historical_mean=float(returns.mean()),
    )
    bullish_paths = scenario_paths_from_sampled_returns(
        base,
        start_value=10000,
        assumptions=scenario_assumptions("bullish", {}),
        historical_mean=float(returns.mean()),
    )

    assert neutral_paths.shape == bullish_paths.shape == (100, 11)


def test_bullish_preset_applies_positive_drift_and_lower_volatility():
    sampled = np.array([[-0.02, 0.0, 0.02]])
    neutral = transform_scenario_returns(sampled, 0.0, scenario_assumptions("neutral", {}))
    bullish = transform_scenario_returns(sampled, 0.0, scenario_assumptions("bullish", {}))

    assert scenario_assumptions("bullish", {})["drift_shift_annual"] > 0
    assert scenario_assumptions("bullish", {})["volatility_multiplier"] < 1
    assert bullish.mean() > neutral.mean()
    assert bullish.std() < neutral.std()


def test_bearish_preset_applies_negative_drift_and_higher_volatility():
    sampled = np.array([[-0.02, 0.0, 0.02]])
    neutral = transform_scenario_returns(sampled, 0.0, scenario_assumptions("neutral", {}))
    bearish = transform_scenario_returns(sampled, 0.0, scenario_assumptions("bearish", {}))

    assert scenario_assumptions("bearish", {})["drift_shift_annual"] < 0
    assert scenario_assumptions("bearish", {})["volatility_multiplier"] > 1
    assert bearish.mean() < neutral.mean()
    assert bearish.std() > neutral.std()


def test_crash_initial_shock_is_applied_once():
    sampled = np.zeros((1, 3))
    assumptions = {
        "drift_shift_annual": 0.0,
        "volatility_multiplier": 1.0,
        "initial_shock_pct": -0.15,
    }

    paths = scenario_paths_from_sampled_returns(
        sampled,
        start_value=10000,
        assumptions=assumptions,
        historical_mean=0.0,
    )

    assert np.allclose(paths[0], [10000, 8500, 8500, 8500])


def test_no_simulated_return_is_below_negative_one_hundred_percent():
    sampled = np.array([[-5.0, -2.0, 0.01]])

    transformed = transform_scenario_returns(sampled, 0.0, scenario_assumptions("crash", {}))

    assert np.min(transformed) >= -0.999999


def test_percentile_paths_contain_days_plus_one_values():
    result = run_portfolio_scenario_monte_carlo(
        synthetic_returns(),
        days=15,
        simulations=120,
        block_size=3,
        seed=42,
        scenarios=["neutral"],
    )

    scenario = result["artifact"]["scenarios"]["neutral"]
    assert len(scenario["percentile_paths"]["p50"]) == 16
    assert scenario["percentile_paths"]["p50"][0] == 10000
