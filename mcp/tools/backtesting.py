from __future__ import annotations

import math
import uuid
from typing import Any

import pandas as pd

from tools.formatting import series_to_points


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if hasattr(value, "iloc"):
            value = value.iloc[0]
        cleaned = float(value)
        if math.isfinite(cleaned):
            return cleaned
    except Exception:
        return default
    return default


def _safe_metric(callable_metric, multiplier: float = 1.0, default: float | None = None):
    try:
        return _safe_float(callable_metric(), default=default) * multiplier
    except Exception:
        return default


def _records_to_dicts(records: Any) -> list[dict[str, Any]]:
    try:
        if isinstance(records, pd.DataFrame):
            return records.to_dict(orient="records")
    except Exception:
        return []
    return []


def _trade_records(portfolio: Any) -> list[dict[str, Any]]:
    try:
        return _records_to_dicts(portfolio.trades.records_readable)
    except Exception:
        return []


def _drawdown_curve(equity_curve: pd.Series) -> pd.Series:
    running_max = equity_curve.cummax()
    return (equity_curve / running_max - 1.0).fillna(0.0)


def run_vectorbt_backtest(
    df: pd.DataFrame,
    entries: pd.Series,
    exits: pd.Series,
    initial_cash: float = 10000,
    fees: float = 0.001,
) -> dict[str, Any]:
    try:
        import vectorbt as vbt
    except ImportError as exc:
        raise RuntimeError("vectorbt is not installed. Install this project with pip install -e .") from exc

    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive.")
    if fees < 0:
        raise ValueError("fees must be greater than or equal to zero.")

    close = pd.to_numeric(df["close"], errors="coerce")
    if "time" in df.columns:
        close.index = pd.Index(df["time"].astype(str), name="time")
    close = close.dropna()
    aligned_entries = entries.reindex(close.index).fillna(False).astype(bool)
    aligned_exits = exits.reindex(close.index).fillna(False).astype(bool)
    warnings: list[str] = []

    portfolio = vbt.Portfolio.from_signals(
        close,
        aligned_entries,
        aligned_exits,
        init_cash=initial_cash,
        fees=fees,
        freq="1D",
    )

    equity = portfolio.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]
    equity = pd.Series(equity, index=close.index, name="equity")
    drawdown = _drawdown_curve(equity)
    trades = _trade_records(portfolio)

    total_return_pct = _safe_metric(portfolio.total_return, multiplier=100.0, default=0.0)
    sharpe_ratio = _safe_metric(portfolio.sharpe_ratio, default=None)
    max_drawdown = _safe_metric(portfolio.max_drawdown, multiplier=100.0, default=None)
    if max_drawdown is not None:
        max_drawdown = -abs(max_drawdown)

    try:
        total_trades = int(portfolio.trades.count())
    except Exception:
        total_trades = len(trades)
        warnings.append("trade_count_unavailable")

    try:
        win_rate_pct = _safe_float(portfolio.trades.win_rate(), default=None)
        if win_rate_pct is not None:
            win_rate_pct *= 100
    except Exception:
        win_rate_pct = None
        warnings.append("win_rate_unavailable")

    final_value = _safe_float(equity.iloc[-1], default=float(initial_cash))
    metrics = {
        "total_return_pct": round(total_return_pct or 0.0, 2),
        "sharpe_ratio": round(sharpe_ratio, 2) if sharpe_ratio is not None else None,
        "max_drawdown_pct": round(max_drawdown, 2) if max_drawdown is not None else None,
        "win_rate_pct": round(win_rate_pct, 2) if win_rate_pct is not None else None,
        "total_trades": total_trades,
        "final_value": round(final_value or float(initial_cash), 2),
    }

    return {
        "run_id": f"bt_{uuid.uuid4().hex[:6]}",
        "metrics": metrics,
        "equity_curve": series_to_points(equity),
        "drawdown_curve": series_to_points(drawdown),
        "trades": trades,
        "warnings": warnings,
    }
