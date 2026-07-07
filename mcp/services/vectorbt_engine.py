from __future__ import annotations

import math
import uuid
from typing import Any

import numpy as np
import pandas as pd

from tools.backtesting import run_vectorbt_backtest
from tools.formatting import series_to_points


class VectorBTEngine:
    def run_single_asset_backtest(
        self,
        df: pd.DataFrame,
        entries: pd.Series,
        exits: pd.Series,
        *,
        initial_cash: float,
        fees: float,
    ) -> dict[str, Any]:
        return run_vectorbt_backtest(
            df,
            entries,
            exits,
            initial_cash=initial_cash,
            fees=fees,
        )

    def equity_returns(self, backtest: dict[str, Any]) -> pd.Series:
        points = backtest.get("equity_curve") if isinstance(backtest, dict) else []
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError("Backtest equity curve is required for strategy-return Monte Carlo.")
        series = pd.Series(
            [point.get("value") for point in points if isinstance(point, dict)],
            index=[point.get("time") for point in points if isinstance(point, dict)],
            dtype=float,
        ).replace([np.inf, -np.inf], np.nan).dropna()
        returns = series.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        if returns.empty:
            raise ValueError("Backtest equity curve did not produce valid strategy returns.")
        returns.name = "strategy_return"
        return returns

    def run_weighted_portfolio_backtest(
        self,
        returns: pd.DataFrame,
        weights: dict[str, float],
        *,
        initial_cash: float,
    ) -> dict[str, Any]:
        weight_series = pd.Series(weights, dtype=float).reindex(returns.columns).fillna(0.0)
        portfolio_returns = returns.mul(weight_series, axis=1).sum(axis=1)
        portfolio_returns = portfolio_returns.replace([np.inf, -np.inf], np.nan).dropna()
        if portfolio_returns.empty:
            raise ValueError("No valid optimized portfolio returns were available.")
        equity = float(initial_cash) * (1.0 + portfolio_returns).cumprod()
        equity.iloc[0] = float(initial_cash) * (1.0 + portfolio_returns.iloc[0])
        drawdown = _drawdown_curve(equity)
        metrics = _portfolio_return_metrics(portfolio_returns, equity)
        return {
            "run_id": f"portfolio_bt_{uuid.uuid4().hex[:8]}",
            "returns": portfolio_returns,
            "metrics": metrics,
            "equity_curve": series_to_points(equity.rename("equity")),
            "drawdown_curve": series_to_points(drawdown.rename("drawdown")),
            "trades": [],
            "warnings": [],
        }


def _drawdown_curve(equity: pd.Series) -> pd.Series:
    running_max = equity.cummax()
    return (equity / running_max - 1.0).fillna(0.0)


def _portfolio_return_metrics(returns: pd.Series, equity: pd.Series) -> dict[str, Any]:
    periods_per_year = 252
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) > 1 else 0.0
    volatility = float(returns.std(ddof=1) * math.sqrt(periods_per_year)) if len(returns) > 1 else 0.0
    annual_return = float((1.0 + returns).prod() ** (periods_per_year / max(len(returns), 1)) - 1.0)
    sharpe = annual_return / volatility if volatility > 0 else 0.0
    drawdown = _drawdown_curve(equity)
    return {
        "total_return_pct": round(total_return * 100.0, 2),
        "expected_annual_return_pct": round(annual_return * 100.0, 2),
        "annual_volatility_pct": round(volatility * 100.0, 2),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown_pct": round(abs(float(drawdown.min())) * 100.0, 2),
        "final_value": round(float(equity.iloc[-1]), 2),
    }

