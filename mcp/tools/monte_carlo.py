from __future__ import annotations

import math
import uuid
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS = 252
SCENARIO_NAMES = ("neutral", "bullish", "bearish", "crash")
SCENARIO_LABELS = {
    "neutral": "Neutral",
    "bullish": "Bullish",
    "bearish": "Bearish",
    "crash": "Crash",
}
SCENARIO_PRESETS = {
    "neutral": {
        "drift_shift_annual": 0.0,
        "volatility_multiplier": 1.0,
        "initial_shock_pct": 0.0,
    },
    "bullish": {
        "drift_shift_annual": 0.08,
        "volatility_multiplier": 0.85,
        "initial_shock_pct": 0.0,
    },
    "bearish": {
        "drift_shift_annual": -0.08,
        "volatility_multiplier": 1.25,
        "initial_shock_pct": 0.0,
    },
    "crash": {
        "drift_shift_annual": -0.10,
        "volatility_multiplier": 1.75,
        "initial_shock_pct": -0.15,
    },
}


def _round_list(values: np.ndarray) -> list[float]:
    return [round(float(value), 4) for value in values]


def run_bootstrap_monte_carlo(
    close_prices: pd.Series,
    start_value: float,
    days: int = 60,
    simulations: int = 500,
    seed: int | None = None,
) -> dict[str, Any]:
    if start_value <= 0:
        raise ValueError("start_value must be positive.")
    if days < 1:
        raise ValueError("days must be at least 1.")
    if simulations < 1:
        raise ValueError("simulations must be at least 1.")

    close = pd.to_numeric(pd.Series(close_prices), errors="coerce")
    returns = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    returns = returns[np.isfinite(returns)]
    if returns.empty:
        raise ValueError("At least two valid close prices are required for Monte Carlo simulation.")

    rng = np.random.default_rng(seed)
    sampled_returns = rng.choice(returns.to_numpy(), size=(simulations, days), replace=True)
    growth = np.cumprod(1 + sampled_returns, axis=1)
    paths = np.concatenate(
        [np.full((simulations, 1), float(start_value)), float(start_value) * growth],
        axis=1,
    )
    final_values = paths[:, -1]
    final_returns = final_values / float(start_value) - 1.0

    summary = {
        "expected_return_pct": round(float(np.mean(final_returns) * 100), 2),
        "probability_positive_return_pct": round(float(np.mean(final_returns > 0) * 100), 2),
        "p5_return_pct": round(float(np.percentile(final_returns, 5) * 100), 2),
        "p50_return_pct": round(float(np.percentile(final_returns, 50) * 100), 2),
        "p95_return_pct": round(float(np.percentile(final_returns, 95) * 100), 2),
        "expected_final_value": round(float(np.mean(final_values)), 2),
    }

    percentile_paths = {
        "p5": _round_list(np.percentile(paths, 5, axis=0)),
        "p25": _round_list(np.percentile(paths, 25, axis=0)),
        "p50": _round_list(np.percentile(paths, 50, axis=0)),
        "p75": _round_list(np.percentile(paths, 75, axis=0)),
        "p95": _round_list(np.percentile(paths, 95, axis=0)),
    }
    sample_count = min(20, simulations)
    sample_paths = [_round_list(path) for path in paths[:sample_count]]

    if not math.isfinite(summary["expected_return_pct"]):
        raise ValueError("Monte Carlo simulation produced invalid results.")

    return {
        "run_id": f"mc_{uuid.uuid4().hex[:6]}",
        "summary": summary,
        "percentile_paths": percentile_paths,
        "sample_paths": sample_paths,
    }


def run_portfolio_scenario_monte_carlo(
    portfolio_returns: pd.Series | np.ndarray | list[float],
    start_value: float = 10000,
    days: int = 60,
    simulations: int = 500,
    block_size: int = 5,
    seed: int | None = 42,
    scenarios: list[str] | tuple[str, ...] | None = None,
    scenario_overrides: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    if start_value <= 0:
        raise ValueError("portfolio_start_value must be positive.")

    days = _validate_int_range(days, 1, 252, "monte_carlo_days")
    simulations = _validate_int_range(simulations, 100, 5000, "monte_carlo_simulations")
    block_size = _validate_int_range(block_size, 1, 20, "monte_carlo_block_size")
    scenario_names = _validate_scenarios(scenarios)
    overrides = _validate_scenario_overrides(scenario_overrides or {})

    returns = _clean_returns(portfolio_returns)
    if len(returns) == 0:
        raise ValueError("At least one valid portfolio return is required for scenario analysis.")
    if block_size > len(returns):
        raise ValueError("monte_carlo_block_size cannot exceed available historical observations.")

    sampled_returns = sample_block_bootstrap_returns(
        returns,
        days=days,
        simulations=simulations,
        block_size=block_size,
        seed=seed,
    )
    historical_mean = float(np.mean(returns))
    scenario_artifacts: dict[str, Any] = {}
    compact_scenarios: list[dict[str, Any]] = []

    for name in scenario_names:
        assumptions = scenario_assumptions(name, overrides)
        paths = scenario_paths_from_sampled_returns(
            sampled_returns,
            start_value=float(start_value),
            assumptions=assumptions,
            historical_mean=historical_mean,
        )
        summary = summarize_paths(paths, float(start_value))
        percentile_paths = {
            "p5": _round_list(np.percentile(paths, 5, axis=0)),
            "p25": _round_list(np.percentile(paths, 25, axis=0)),
            "p50": _round_list(np.percentile(paths, 50, axis=0)),
            "p75": _round_list(np.percentile(paths, 75, axis=0)),
            "p95": _round_list(np.percentile(paths, 95, axis=0)),
        }
        sample_paths = [_round_list(path) for path in paths[: min(20, simulations)]]
        scenario_artifacts[name] = {
            "assumptions": assumptions,
            "summary": summary,
            "percentile_paths": percentile_paths,
            "sample_paths": sample_paths,
        }
        compact_scenarios.append(
            {
                "name": name,
                "label": SCENARIO_LABELS[name],
                "assumptions": assumptions,
                "summary": summary,
            }
        )

    config = {
        "enabled": True,
        "days": days,
        "simulations": simulations,
        "block_size": block_size,
        "seed": seed,
        "portfolio_start_value": round(float(start_value), 4),
        "scenarios": list(scenario_names),
    }
    return {
        "compact": {
            **config,
            "scenarios": compact_scenarios,
        },
        "artifact": {
            "config": config,
            "scenarios": scenario_artifacts,
        },
    }


def sample_block_bootstrap_returns(
    returns: pd.Series | np.ndarray | list[float],
    days: int,
    simulations: int,
    block_size: int,
    seed: int | None = None,
) -> np.ndarray:
    cleaned = _clean_returns(returns)
    if block_size > len(cleaned):
        raise ValueError("monte_carlo_block_size cannot exceed available historical observations.")

    rng = np.random.default_rng(seed)
    block_count = int(math.ceil(days / block_size))
    max_start = len(cleaned) - block_size
    paths = np.empty((simulations, block_count * block_size), dtype=float)
    for simulation_index in range(simulations):
        starts = rng.integers(0, max_start + 1, size=block_count)
        sampled_blocks = [cleaned[start : start + block_size] for start in starts]
        paths[simulation_index, :] = np.concatenate(sampled_blocks)
    return paths[:, :days]


def scenario_assumptions(
    scenario: str,
    overrides: dict[str, dict[str, float]] | None = None,
) -> dict[str, float]:
    name = str(scenario or "").strip().lower()
    if name not in SCENARIO_PRESETS:
        raise ValueError(f"invalid_scenario: {scenario}")
    assumptions = dict(SCENARIO_PRESETS[name])
    override = (overrides or {}).get(name) or {}
    assumptions.update(override)
    return _validate_assumptions(assumptions)


def transform_scenario_returns(
    sampled_returns: np.ndarray,
    historical_mean: float,
    assumptions: dict[str, float],
) -> np.ndarray:
    daily_shift = annual_to_daily_drift(assumptions["drift_shift_annual"])
    transformed = (
        float(historical_mean)
        + (np.asarray(sampled_returns, dtype=float) - float(historical_mean))
        * assumptions["volatility_multiplier"]
        + daily_shift
    )
    return np.maximum(transformed, -0.999999)


def scenario_paths_from_sampled_returns(
    sampled_returns: np.ndarray,
    start_value: float,
    assumptions: dict[str, float],
    historical_mean: float,
) -> np.ndarray:
    transformed_returns = transform_scenario_returns(
        sampled_returns,
        historical_mean=historical_mean,
        assumptions=assumptions,
    )
    shock_factor = max(0.0, 1.0 + float(assumptions["initial_shock_pct"]))
    growth = shock_factor * np.cumprod(1.0 + transformed_returns, axis=1)
    future_paths = float(start_value) * growth
    return np.concatenate(
        [np.full((future_paths.shape[0], 1), float(start_value)), future_paths],
        axis=1,
    )


def summarize_paths(paths: np.ndarray, start_value: float) -> dict[str, float]:
    final_values = paths[:, -1]
    final_returns = final_values / float(start_value) - 1.0
    running_peaks = np.maximum.accumulate(paths, axis=1)
    drawdowns = np.divide(paths, running_peaks, out=np.ones_like(paths), where=running_peaks > 0) - 1.0
    max_drawdowns = np.min(drawdowns, axis=1)
    return {
        "expected_return_pct": _round_pct(float(np.mean(final_returns))),
        "probability_positive_return_pct": _round_pct(float(np.mean(final_returns > 0))),
        "probability_loss_above_10_pct": _round_pct(float(np.mean(final_returns < -0.10))),
        "p5_return_pct": _round_pct(float(np.percentile(final_returns, 5))),
        "p25_return_pct": _round_pct(float(np.percentile(final_returns, 25))),
        "p50_return_pct": _round_pct(float(np.percentile(final_returns, 50))),
        "p75_return_pct": _round_pct(float(np.percentile(final_returns, 75))),
        "p95_return_pct": _round_pct(float(np.percentile(final_returns, 95))),
        "expected_final_value": round(float(np.mean(final_values)), 2),
        "p5_final_value": round(float(np.percentile(final_values, 5)), 2),
        "p50_final_value": round(float(np.percentile(final_values, 50)), 2),
        "p95_final_value": round(float(np.percentile(final_values, 95)), 2),
        "average_max_drawdown_pct": _round_pct(abs(float(np.mean(max_drawdowns)))),
        "worst_simulated_drawdown_pct": _round_pct(abs(float(np.min(max_drawdowns)))),
    }


def annual_to_daily_drift(drift_shift_annual: float) -> float:
    return (1.0 + float(drift_shift_annual)) ** (1.0 / TRADING_DAYS) - 1.0


def _validate_int_range(value: int, minimum: int, maximum: int, code: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(code)
    return parsed


def _validate_scenarios(scenarios: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    selected = tuple(str(name or "").strip().lower() for name in (scenarios or SCENARIO_NAMES))
    if not selected:
        raise ValueError("invalid_scenario")
    invalid = [name for name in selected if name not in SCENARIO_NAMES]
    if invalid:
        raise ValueError(f"invalid_scenario: {', '.join(invalid)}")
    return selected


def _validate_scenario_overrides(
    overrides: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    cleaned: dict[str, dict[str, float]] = {}
    allowed_fields = {"drift_shift_annual", "volatility_multiplier", "initial_shock_pct"}
    for raw_name, raw_override in overrides.items():
        name = str(raw_name or "").strip().lower()
        if name not in SCENARIO_NAMES or not isinstance(raw_override, dict):
            raise ValueError("invalid_scenario_override")
        unknown_fields = set(raw_override) - allowed_fields
        if unknown_fields:
            raise ValueError("invalid_scenario_override")
        cleaned[name] = _validate_assumptions(
            {
                **SCENARIO_PRESETS[name],
                **{key: value for key, value in raw_override.items() if value is not None},
            }
        )
    return cleaned


def _validate_assumptions(values: dict[str, float]) -> dict[str, float]:
    try:
        drift_shift_annual = float(values["drift_shift_annual"])
        volatility_multiplier = float(values["volatility_multiplier"])
        initial_shock_pct = float(values["initial_shock_pct"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid_scenario_override") from exc
    if not -0.50 <= drift_shift_annual <= 0.50:
        raise ValueError("invalid_scenario_override")
    if not 0.25 <= volatility_multiplier <= 4.0:
        raise ValueError("invalid_scenario_override")
    if not -0.80 <= initial_shock_pct <= 0.80:
        raise ValueError("invalid_scenario_override")
    return {
        "drift_shift_annual": drift_shift_annual,
        "volatility_multiplier": volatility_multiplier,
        "initial_shock_pct": initial_shock_pct,
    }


def _clean_returns(returns: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    series = pd.to_numeric(pd.Series(returns), errors="coerce")
    series = series.replace([np.inf, -np.inf], np.nan).dropna()
    cleaned = series[np.isfinite(series)].to_numpy(dtype=float)
    if cleaned.size == 0:
        return cleaned
    return cleaned


def _round_pct(value: float) -> float:
    return round(float(value) * 100.0, 2)
