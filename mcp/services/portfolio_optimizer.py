from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from schemas.workflows import OptimizationSettings


TRADING_DAYS = 252


class PortfolioOptimizer:
    def optimize_returns(
        self,
        returns: pd.DataFrame,
        settings: OptimizationSettings,
    ) -> dict[str, Any]:
        returns = _clean_return_frame(returns)
        symbols = list(returns.columns)
        mean_returns, cov_matrix = _annualized_inputs(returns, settings.covariance_regularization)
        result = _solve(symbols, mean_returns, cov_matrix, settings)
        min_vol = _solve(
            symbols,
            mean_returns,
            cov_matrix,
            settings.model_copy(update={"objective": "min_volatility"}),
        )
        max_sharpe = _solve(
            symbols,
            mean_returns,
            cov_matrix,
            settings.model_copy(update={"objective": "max_sharpe"}),
        )
        frontier = _efficient_frontier(symbols, mean_returns, cov_matrix, settings)
        return {
            "weights": result["weights"],
            "metrics": result["metrics"],
            "selected_portfolio": result["portfolio"],
            "min_volatility_portfolio": min_vol["portfolio"],
            "max_sharpe_portfolio": max_sharpe["portfolio"],
            "frontier": frontier,
            "correlation_matrix": _correlation_matrix(returns),
            "expected_returns": {
                symbol: round(float(mean_returns.loc[symbol]), 6) for symbol in symbols
            },
            "warnings": result.get("warnings", []),
        }


def _clean_return_frame(returns: pd.DataFrame) -> pd.DataFrame:
    frame = returns.copy()
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if frame.empty or frame.shape[1] < 2:
        raise ValueError("At least two aligned return series are required for optimization.")
    return frame.astype(float)


def _annualized_inputs(returns: pd.DataFrame, regularization: float) -> tuple[pd.Series, pd.DataFrame]:
    mean_returns = returns.mean() * TRADING_DAYS
    cov_matrix = returns.cov() * TRADING_DAYS
    cov_matrix = cov_matrix.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    diagonal = np.eye(len(cov_matrix)) * float(regularization)
    cov_matrix = pd.DataFrame(
        cov_matrix.to_numpy(dtype=float) + diagonal,
        index=cov_matrix.index,
        columns=cov_matrix.columns,
    )
    return mean_returns, cov_matrix


def _solve(
    symbols: list[str],
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    settings: OptimizationSettings,
) -> dict[str, Any]:
    count = len(symbols)
    initial = np.repeat(float(settings.net_exposure) / count, count)
    bounds = _bounds(count, settings)
    constraints = _constraints(mean_returns, cov_matrix, settings)

    def objective(weights: np.ndarray) -> float:
        expected_return, volatility, sharpe = _metrics(weights, mean_returns, cov_matrix, settings.risk_free_rate)
        if settings.objective == "max_sharpe":
            return -sharpe
        if settings.objective == "min_volatility":
            return volatility
        if settings.objective == "target_return":
            target = float(settings.target_return if settings.target_return is not None else expected_return)
            return volatility + abs(expected_return - target)
        if settings.objective == "target_volatility":
            target = float(settings.target_volatility if settings.target_volatility is not None else volatility)
            return abs(volatility - target) - expected_return
        return -sharpe

    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    warnings: list[str] = []
    if not result.success:
        warnings.append(f"optimizer_primary_failed:{result.message}")
        fallback = settings.model_copy(update={"objective": "min_volatility"})
        if fallback.objective != settings.objective:
            return _solve(symbols, mean_returns, cov_matrix, fallback)
        raise ValueError(f"Portfolio optimization failed: {result.message}")

    weights = _clean_weights(result.x)
    portfolio = _portfolio_point(symbols, weights, mean_returns, cov_matrix, settings.risk_free_rate)
    return {
        "weights": dict(portfolio["weights"]),
        "metrics": {
            "expected_annual_return_pct": round(portfolio["portfolio_return"] * 100.0, 2),
            "annual_volatility_pct": round(portfolio["portfolio_volatility"] * 100.0, 2),
            "sharpe_ratio": round(portfolio["sharpe_ratio"], 4),
            "gross_exposure": round(float(np.sum(np.abs(weights))), 6),
            "net_exposure": round(float(np.sum(weights)), 6),
        },
        "portfolio": portfolio,
        "warnings": warnings,
    }


def _bounds(count: int, settings: OptimizationSettings) -> list[tuple[float, float]]:
    minimum = settings.min_weight
    if minimum is None:
        minimum = -settings.max_weight if settings.allow_short else 0.0
    if not settings.allow_short:
        minimum = max(0.0, float(minimum))
    return [(float(minimum), float(settings.max_weight)) for _ in range(count)]


def _constraints(
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    settings: OptimizationSettings,
) -> list[dict[str, Any]]:
    mean_array = mean_returns.to_numpy(dtype=float)
    cov_array = cov_matrix.to_numpy(dtype=float)
    constraints: list[dict[str, Any]] = [
        {"type": "eq", "fun": lambda weights: float(np.sum(weights) - settings.net_exposure)},
        {
            "type": "ineq",
            "fun": lambda weights: float(settings.gross_exposure_limit - np.sum(np.abs(weights))),
        },
    ]
    if settings.target_return is not None:
        constraints.append(
            {
                "type": "ineq",
                "fun": lambda weights: float(np.dot(weights, mean_array) - float(settings.target_return)),
            }
        )
    if settings.target_volatility is not None:
        constraints.append(
            {
                "type": "ineq",
                "fun": lambda weights: float(
                    float(settings.target_volatility)
                    - math.sqrt(max(float(np.dot(weights.T, np.dot(cov_array, weights))), 0.0))
                ),
            }
        )
    return constraints


def _metrics(
    weights: np.ndarray,
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float,
) -> tuple[float, float, float]:
    mean_array = mean_returns.to_numpy(dtype=float)
    cov_array = cov_matrix.to_numpy(dtype=float)
    expected_return = float(np.dot(weights, mean_array))
    variance = max(float(np.dot(weights.T, np.dot(cov_array, weights))), 0.0)
    volatility = math.sqrt(variance)
    sharpe = 0.0 if volatility <= 0 else (expected_return - float(risk_free_rate)) / volatility
    return expected_return, volatility, sharpe


def _portfolio_point(
    symbols: list[str],
    weights: np.ndarray,
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float,
) -> dict[str, Any]:
    expected_return, volatility, sharpe = _metrics(weights, mean_returns, cov_matrix, risk_free_rate)
    if not all(math.isfinite(value) for value in (expected_return, volatility, sharpe)):
        raise ValueError("Portfolio optimization returned non-finite metrics.")
    return {
        "portfolio_volatility": round(volatility, 6),
        "portfolio_return": round(expected_return, 6),
        "sharpe_ratio": round(sharpe, 4),
        "weights": {
            symbol: round(float(weight), 6)
            for symbol, weight in zip(symbols, weights, strict=True)
        },
    }


def _efficient_frontier(
    symbols: list[str],
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    settings: OptimizationSettings,
) -> list[dict[str, Any]]:
    count = min(max(settings.num_frontier_portfolios, 50), 250)
    min_return = float(mean_returns.min())
    max_return = float(mean_returns.max())
    if math.isclose(min_return, max_return):
        return []
    points: list[dict[str, Any]] = []
    for target in np.linspace(min_return, max_return, count):
        try:
            target_settings = settings.model_copy(
                update={"objective": "target_return", "target_return": float(target)}
            )
            solved = _solve(symbols, mean_returns, cov_matrix, target_settings)
            point = dict(solved["selected_portfolio"] if "selected_portfolio" in solved else solved["portfolio"])
            point.pop("weights", None)
            points.append(point)
        except Exception:
            continue
    return _dedupe(points)


def _correlation_matrix(returns: pd.DataFrame) -> list[dict[str, Any]]:
    corr = returns.corr().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for symbol in corr.columns:
        row: dict[str, Any] = {"symbol": str(symbol)}
        for other in corr.columns:
            row[str(other)] = round(float(corr.loc[symbol, other]), 4)
        rows.append(row)
    return rows


def _clean_weights(weights: np.ndarray) -> np.ndarray:
    cleaned = np.asarray(weights, dtype=float)
    cleaned[np.abs(cleaned) < 1e-10] = 0.0
    return cleaned


def _dedupe(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[float, float]] = set()
    cleaned: list[dict[str, Any]] = []
    for point in points:
        key = (
            round(float(point.get("portfolio_volatility", 0.0)), 6),
            round(float(point.get("portfolio_return", 0.0)), 6),
        )
        if key not in seen:
            seen.add(key)
            cleaned.append(point)
    return sorted(cleaned, key=lambda item: float(item.get("portfolio_volatility", 0.0)))
