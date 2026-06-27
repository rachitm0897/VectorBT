import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import vectorbt as vbt
from django.conf import settings

from apps.market_data.finnhub import MarketDataError, fetch_daily_ohlcv
from apps.market_data.symbols import normalize_symbol
from apps.strategies.registry import StrategyValidationError, build_strategy_signals
from apps.analytics.services import persist_backtest_result, persist_portfolio_optimization_result
from apps.analytics.services import persist_factor_portfolio_result


class BacktestExecutionError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def run_backtest(
    validated_request: dict,
    finnhub_api_key: str | None = None,
    analytics_source: str = "api",
) -> dict:
    if settings.MCP_ENABLED:
        from apps.backtesting.mcp_client import MCPClientError, run_remote_backtest

        try:
            result = run_remote_backtest(validated_request, finnhub_api_key=finnhub_api_key)
        except MCPClientError as exc:
            raise BacktestExecutionError(exc.code, str(exc)) from exc
    else:
        result = run_local_backtest(validated_request, finnhub_api_key=finnhub_api_key)

    if result.get("status") == "success":
        analytics_result = dict(result)
        analytics_result["_analytics_request"] = dict(validated_request)
        _apply_explicit_analytics_run_id(analytics_result, validated_request)
        persist_backtest_result(analytics_result, source=analytics_source)
    return result


def run_structured_backtest(
    payload: dict,
    finnhub_api_key: str | None = None,
    analytics_source: str = "api",
) -> dict:
    return run_backtest(payload, finnhub_api_key=finnhub_api_key, analytics_source=analytics_source)


def run_portfolio_optimization(
    validated_request: dict,
    finnhub_api_key: str | None = None,
    analytics_source: str = "api",
) -> dict:
    if not settings.MCP_ENABLED:
        raise BacktestExecutionError(
            "mcp_disabled",
            "Portfolio optimization requires the MCP server.",
        )

    from apps.backtesting.mcp_client import MCPClientError, run_remote_portfolio_optimization

    try:
        result = run_remote_portfolio_optimization(validated_request, finnhub_api_key=finnhub_api_key)
    except MCPClientError as exc:
        raise BacktestExecutionError(exc.code, str(exc)) from exc

    if result.get("status") == "success":
        analytics_result = dict(result)
        analytics_result["_analytics_request"] = dict(validated_request)
        _apply_explicit_analytics_run_id(analytics_result, validated_request)
        persist_portfolio_optimization_result(analytics_result, source=analytics_source)
    return result


def run_structured_portfolio_optimization(
    payload: dict,
    finnhub_api_key: str | None = None,
    analytics_source: str = "api",
) -> dict:
    return run_portfolio_optimization(payload, finnhub_api_key=finnhub_api_key, analytics_source=analytics_source)


def run_factor_portfolio(
    validated_request: dict,
    finnhub_api_key: str | None = None,
    analytics_source: str = "api",
) -> dict:
    if not settings.MCP_ENABLED:
        raise BacktestExecutionError(
            "mcp_disabled",
            "Factor portfolio construction requires the MCP server.",
        )

    from apps.backtesting.mcp_client import MCPClientError, run_remote_factor_portfolio

    try:
        result = run_remote_factor_portfolio(validated_request, finnhub_api_key=finnhub_api_key)
    except MCPClientError as exc:
        raise BacktestExecutionError(exc.code, str(exc)) from exc

    if result.get("status") == "success":
        analytics_result = dict(result)
        analytics_result["_analytics_request"] = dict(validated_request)
        _apply_explicit_analytics_run_id(analytics_result, validated_request)
        persist_factor_portfolio_result(analytics_result, source=analytics_source)
    return result


def _apply_explicit_analytics_run_id(result: dict, validated_request: dict) -> None:
    run_id = validated_request.get("run_id") or validated_request.get("_analytics_run_id")
    if run_id:
        result["run_id"] = str(run_id)


def run_local_backtest(validated_request: dict, finnhub_api_key: str | None = None) -> dict:
    symbol = normalize_symbol(validated_request["symbol"])
    start_ts, end_ts = _lookback_to_timestamps(validated_request.get("lookback", "2y"))
    frame = fetch_daily_ohlcv(
        symbol,
        validated_request.get("resolution", "D"),
        start_ts,
        end_ts,
        api_key=finnhub_api_key,
    )

    close = _close_series(frame)
    strategy_result = build_strategy_signals(
        validated_request["strategy"],
        close,
        validated_request.get("parameters") or {},
    )

    portfolio = vbt.Portfolio.from_signals(
        close,
        strategy_result.entries,
        strategy_result.exits,
        init_cash=float(validated_request.get("initial_cash", 10000.0)),
        fees=float(validated_request.get("fees", 0.0)),
        freq="1D",
    )

    equity = portfolio.value()
    final_value = _safe_float(equity.iloc[-1], default=float(validated_request.get("initial_cash", 10000.0)))
    monte_carlo_config = validated_request.get("monte_carlo") or {"enabled": False}
    monte_carlo, monte_carlo_summary, monte_carlo_warnings = _run_monte_carlo(
        close=close,
        start_value=final_value,
        config=monte_carlo_config,
    )

    warnings = [*strategy_result.warnings, *monte_carlo_warnings]

    return {
        "status": "success",
        "message": "Backtest completed successfully.",
        "request": {
            "symbol": symbol,
            "strategy": validated_request["strategy"],
            "parameters": strategy_result.parameters,
        },
        "metrics": _portfolio_metrics(portfolio, equity, final_value),
        "charts": {
            "price": _price_chart(frame),
            "signals": _signals_chart(close, strategy_result.entries, strategy_result.exits),
            "equity_curve": _series_chart(equity, "value"),
            "drawdown_curve": _drawdown_chart(equity),
            "monte_carlo": monte_carlo,
        },
        "tables": {
            "trades": _trades_table(portfolio),
        },
        "summary": monte_carlo_summary,
        "warnings": warnings,
        "errors": [],
    }


def _lookback_to_timestamps(lookback: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)([dmy])", lookback)
    if not match:
        raise BacktestExecutionError("invalid_lookback", "lookback must use a format like 60d, 6m, or 2y.")

    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        raise BacktestExecutionError("invalid_lookback", "lookback must be greater than zero.")

    days_by_unit = {"d": 1, "m": 30, "y": 365}
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=amount * days_by_unit[unit])
    start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).replace(microsecond=0)
    return int(start.timestamp()), int(end.timestamp())


def _close_series(frame: pd.DataFrame) -> pd.Series:
    close = frame.set_index("date")["close"].astype(float)
    close.index = pd.to_datetime(close.index)
    close.name = "close"
    return close


def _portfolio_metrics(portfolio: vbt.Portfolio, equity: pd.Series, final_value: float) -> dict:
    total_return = _call_float(portfolio.total_return)
    sharpe_ratio = _call_float(portfolio.sharpe_ratio)
    max_drawdown = _call_float(portfolio.max_drawdown)
    win_rate = _call_float(portfolio.trades.win_rate)

    try:
        total_trades = int(portfolio.trades.count())
    except Exception:
        total_trades = 0

    if len(equity) > 0:
        final_value = _safe_float(equity.iloc[-1], default=final_value)

    return {
        "total_return_pct": _round(total_return * 100),
        "sharpe_ratio": _round(sharpe_ratio),
        "max_drawdown_pct": _round(abs(max_drawdown) * 100),
        "win_rate_pct": _round(win_rate * 100),
        "total_trades": total_trades,
        "final_value": _round(final_value),
    }


def _price_chart(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "date": row["date"].date().isoformat(),
                "open": _round(row["open"]),
                "high": _round(row["high"]),
                "low": _round(row["low"]),
                "close": _round(row["close"]),
                "volume": int(row["volume"]),
            }
        )
    return rows


def _signals_chart(close: pd.Series, entries: pd.Series, exits: pd.Series) -> list[dict]:
    signals = []
    for timestamp, enabled in entries.items():
        if bool(enabled):
            signals.append(
                {
                    "date": timestamp.date().isoformat(),
                    "type": "entry",
                    "price": _round(close.loc[timestamp]),
                }
            )
    for timestamp, enabled in exits.items():
        if bool(enabled):
            signals.append(
                {
                    "date": timestamp.date().isoformat(),
                    "type": "exit",
                    "price": _round(close.loc[timestamp]),
                }
            )
    return sorted(signals, key=lambda item: item["date"])


def _drawdown_chart(equity: pd.Series) -> list[dict]:
    running_max = equity.cummax()
    drawdown = (equity / running_max) - 1
    return _series_chart(drawdown * 100, "drawdown_pct")


def _series_chart(series: pd.Series, value_key: str) -> list[dict]:
    rows = []
    for timestamp, value in series.items():
        rows.append({"date": timestamp.date().isoformat(), value_key: _round(value)})
    return rows


def _trades_table(portfolio: vbt.Portfolio) -> list[dict]:
    try:
        records = portfolio.trades.records_readable.copy()
    except Exception:
        return []

    if records.empty:
        return []

    records.columns = [_snake_case(str(column)) for column in records.columns]
    rows = []
    for _, row in records.head(200).iterrows():
        item = {}
        for key, value in row.items():
            item[key] = _json_value(value)
        rows.append(item)
    return rows


def _run_monte_carlo(close: pd.Series, start_value: float, config: dict) -> tuple[dict, dict, list[str]]:
    empty_chart = {"p5": [], "p25": [], "p50": [], "p75": [], "p95": [], "sample_paths": []}
    empty_summary = {
        "monte_carlo_expected_return_pct": 0,
        "probability_positive_return_pct": 0,
        "p5_return_pct": 0,
        "p95_return_pct": 0,
    }

    if not config.get("enabled", False):
        return empty_chart, empty_summary, []

    method = config.get("method", "bootstrap")
    if method != "bootstrap":
        raise BacktestExecutionError("invalid_monte_carlo_method", "Only bootstrap Monte Carlo is supported.")

    returns = close.pct_change().dropna().replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    if len(returns) == 0:
        return empty_chart, empty_summary, ["monte_carlo_insufficient_returns"]

    days = int(config.get("days", 60))
    simulations = int(config.get("simulations", 500))
    rng = np.random.default_rng(42)

    sampled_returns = rng.choice(returns, size=(simulations, days), replace=True)
    future_paths = start_value * np.cumprod(1 + sampled_returns, axis=1)
    paths = np.concatenate([np.full((simulations, 1), start_value), future_paths], axis=1)

    percentiles = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
    end_returns = (paths[:, -1] / start_value) - 1

    chart = {
        "p5": _path_points(percentiles[0]),
        "p25": _path_points(percentiles[1]),
        "p50": _path_points(percentiles[2]),
        "p75": _path_points(percentiles[3]),
        "p95": _path_points(percentiles[4]),
        "sample_paths": [
            {"path": index, "values": _path_points(paths[index])}
            for index in range(min(20, simulations))
        ],
    }

    summary = {
        "monte_carlo_expected_return_pct": _round(float(np.mean(end_returns)) * 100),
        "probability_positive_return_pct": _round(float(np.mean(end_returns > 0)) * 100),
        "p5_return_pct": _round(float(np.percentile(end_returns, 5)) * 100),
        "p95_return_pct": _round(float(np.percentile(end_returns, 95)) * 100),
    }

    return chart, summary, []


def _path_points(values: np.ndarray) -> list[dict]:
    return [{"day": int(index), "value": _round(value)} for index, value in enumerate(values)]


def _call_float(function: Any) -> float:
    try:
        return _safe_float(function(), default=0.0)
    except Exception:
        return 0.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _round(value: Any, places: int = 4) -> float:
    return round(_safe_float(value), places)


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return _round(value)
    if isinstance(value, float):
        return _round(value)
    if isinstance(value, int):
        return value
    return str(value)


def _snake_case(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "value"
