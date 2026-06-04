import pandas as pd

from tools.monte_carlo import run_bootstrap_monte_carlo


def test_monte_carlo_returns_summary():
    close = pd.Series([100, 101, 102, 99, 103, 105, 104, 106, 108, 107])
    result = run_bootstrap_monte_carlo(
        close,
        start_value=10000,
        days=10,
        simulations=100,
        seed=42,
    )

    assert result["run_id"].startswith("mc_")
    assert "summary" in result
    assert "expected_return_pct" in result["summary"]
    assert "expected_final_value" in result["summary"]


def test_monte_carlo_percentile_paths_exist():
    close = pd.Series([100, 101, 102, 99, 103, 105, 104, 106, 108, 107])
    result = run_bootstrap_monte_carlo(
        close,
        start_value=10000,
        days=10,
        simulations=100,
        seed=42,
    )

    assert set(result["percentile_paths"]) == {"p5", "p25", "p50", "p75", "p95"}
    assert len(result["percentile_paths"]["p50"]) == 11
    assert result["sample_paths"]


def test_probability_positive_is_between_zero_and_one_hundred():
    close = pd.Series([100, 101, 102, 99, 103, 105, 104, 106, 108, 107])
    result = run_bootstrap_monte_carlo(
        close,
        start_value=10000,
        days=10,
        simulations=100,
        seed=42,
    )

    probability = result["summary"]["probability_positive_return_pct"]
    assert 0 <= probability <= 100
