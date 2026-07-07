from __future__ import annotations

import math
import uuid
from typing import Any

import numpy as np
import pandas as pd

from schemas.workflows import MonteCarloSettings


class MonteCarloEngine:
    def simulate_returns(
        self,
        returns: pd.Series | pd.DataFrame | np.ndarray | list[float],
        *,
        start_value: float,
        settings: MonteCarloSettings,
    ) -> dict[str, Any]:
        cleaned = _clean_returns(returns)
        if cleaned.size == 0:
            raise ValueError("At least one valid return is required for Monte Carlo simulation.")
        if start_value <= 0:
            raise ValueError("start_value must be positive.")

        if settings.method == "block_bootstrap":
            sampled = _sample_block_bootstrap(
                cleaned,
                days=settings.days,
                simulations=settings.simulations,
                block_size=min(settings.block_size, len(cleaned)),
                seed=settings.seed,
            )
        else:
            rng = np.random.default_rng(settings.seed)
            sampled = rng.choice(cleaned, size=(settings.simulations, settings.days), replace=True)

        sampled = np.maximum(sampled, -0.999999)
        growth = np.cumprod(1.0 + sampled, axis=1)
        paths = np.concatenate(
            [np.full((settings.simulations, 1), float(start_value)), float(start_value) * growth],
            axis=1,
        )
        final_values = paths[:, -1]
        final_returns = final_values / float(start_value) - 1.0
        running_peaks = np.maximum.accumulate(paths, axis=1)
        drawdowns = np.divide(paths, running_peaks, out=np.ones_like(paths), where=running_peaks > 0) - 1.0
        max_drawdowns = np.min(drawdowns, axis=1)
        terminal_bins = _histogram(final_values)
        percentile_paths = {
            key: _round_list(np.percentile(paths, percentile, axis=0))
            for key, percentile in {"p5": 5, "p25": 25, "p50": 50, "p75": 75, "p95": 95}.items()
        }
        downside = final_returns[final_returns < 0]
        threshold_probs = {
            str(threshold): round(float(np.mean(final_returns <= float(threshold))) * 100.0, 2)
            for threshold in settings.thresholds
        }
        result = {
            "run_id": f"mc_{uuid.uuid4().hex[:8]}",
            "method": settings.method,
            "mode": settings.mode,
            "seed": settings.seed,
            "simulation_count": settings.simulations,
            "horizon": settings.days,
            "percentile_paths": percentile_paths,
            "terminal_distribution": {
                "bins": terminal_bins,
                "p5_final_value": round(float(np.percentile(final_values, 5)), 2),
                "p50_final_value": round(float(np.percentile(final_values, 50)), 2),
                "p95_final_value": round(float(np.percentile(final_values, 95)), 2),
            },
            "probability_of_loss_pct": round(float(np.mean(final_returns < 0)) * 100.0, 2),
            "expected_terminal_value": round(float(np.mean(final_values)), 2),
            "downside_percentiles": {
                "p1_return_pct": _pct(np.percentile(final_returns, 1)),
                "p5_return_pct": _pct(np.percentile(final_returns, 5)),
                "p10_return_pct": _pct(np.percentile(final_returns, 10)),
            },
            "expected_shortfall_pct": _pct(np.mean(downside)) if downside.size else 0.0,
            "drawdown_distribution": {
                "average_max_drawdown_pct": _pct(abs(float(np.mean(max_drawdowns)))),
                "p95_max_drawdown_pct": _pct(abs(float(np.percentile(max_drawdowns, 5)))),
                "worst_simulated_drawdown_pct": _pct(abs(float(np.min(max_drawdowns)))),
            },
            "threshold_breach_probabilities_pct": threshold_probs,
            "summary": {
                "expected_return_pct": _pct(float(np.mean(final_returns))),
                "probability_positive_return_pct": round(float(np.mean(final_returns > 0)) * 100.0, 2),
                "probability_of_loss_pct": round(float(np.mean(final_returns < 0)) * 100.0, 2),
                "p5_return_pct": _pct(np.percentile(final_returns, 5)),
                "p50_return_pct": _pct(np.percentile(final_returns, 50)),
                "p95_return_pct": _pct(np.percentile(final_returns, 95)),
                "expected_final_value": round(float(np.mean(final_values)), 2),
            },
        }
        if not math.isfinite(result["summary"]["expected_return_pct"]):
            raise ValueError("Monte Carlo simulation produced invalid results.")
        return result


def _clean_returns(returns: pd.Series | pd.DataFrame | np.ndarray | list[float]) -> np.ndarray:
    if isinstance(returns, pd.DataFrame):
        if returns.shape[1] != 1:
            raise ValueError("Monte Carlo returns input must be a single return series.")
        values = returns.iloc[:, 0]
    else:
        values = returns
    series = pd.to_numeric(pd.Series(values), errors="coerce")
    series = series.replace([np.inf, -np.inf], np.nan).dropna()
    return series[np.isfinite(series)].to_numpy(dtype=float)


def _sample_block_bootstrap(
    returns: np.ndarray,
    *,
    days: int,
    simulations: int,
    block_size: int,
    seed: int | None,
) -> np.ndarray:
    if block_size < 1:
        block_size = 1
    rng = np.random.default_rng(seed)
    block_count = int(math.ceil(days / block_size))
    max_start = max(0, len(returns) - block_size)
    paths = np.empty((simulations, block_count * block_size), dtype=float)
    for simulation_index in range(simulations):
        starts = rng.integers(0, max_start + 1, size=block_count)
        blocks = [returns[start : start + block_size] for start in starts]
        paths[simulation_index, :] = np.concatenate(blocks)
    return paths[:, :days]


def _histogram(values: np.ndarray, bins: int = 20) -> list[dict[str, float]]:
    counts, edges = np.histogram(values, bins=bins)
    total = max(int(np.sum(counts)), 1)
    return [
        {
            "lower": round(float(edges[index]), 2),
            "upper": round(float(edges[index + 1]), 2),
            "count": int(count),
            "probability_pct": round(float(count) / total * 100.0, 2),
        }
        for index, count in enumerate(counts)
    ]


def _round_list(values: np.ndarray) -> list[float]:
    return [round(float(value), 4) for value in values]


def _pct(value: float) -> float:
    return round(float(value) * 100.0, 2)

