from __future__ import annotations

import math
import uuid
from typing import Any

import numpy as np
import pandas as pd


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
