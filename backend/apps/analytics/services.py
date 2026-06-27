from __future__ import annotations

import json
import logging
import math
import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from django.conf import settings


logger = logging.getLogger(__name__)

SENSITIVE_FIELD_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
)


def analytics_enabled() -> bool:
    value = getattr(settings, "ANALYTICS_ENABLED", os.getenv("ANALYTICS_ENABLED", "false"))
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def get_analytics_connection():
    import psycopg

    return psycopg.connect(
        dbname=getattr(settings, "ANALYTICS_DB_NAME", os.getenv("ANALYTICS_DB_NAME", "analytics")),
        user=getattr(settings, "ANALYTICS_DB_USER", os.getenv("ANALYTICS_DB_USER", "analytics_writer")),
        password=getattr(
            settings,
            "ANALYTICS_DB_PASSWORD",
            os.getenv("ANALYTICS_DB_PASSWORD", "analytics_writer_password"),
        ),
        host=getattr(settings, "ANALYTICS_DB_HOST", os.getenv("ANALYTICS_DB_HOST", "localhost")),
        port=int(getattr(settings, "ANALYTICS_DB_PORT", os.getenv("ANALYTICS_DB_PORT", "5432"))),
        connect_timeout=3,
    )


def analytics_status() -> dict[str, Any]:
    response = {
        "enabled": analytics_enabled(),
        "connected": False,
        "database": getattr(settings, "ANALYTICS_DB_NAME", os.getenv("ANALYTICS_DB_NAME", "analytics")),
        "host": getattr(settings, "ANALYTICS_DB_HOST", os.getenv("ANALYTICS_DB_HOST", "localhost")),
        "metabase_url": getattr(settings, "METABASE_URL", os.getenv("METABASE_URL", "http://localhost:3000")),
        "error": None,
    }
    if not response["enabled"]:
        return response

    try:
        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        response["connected"] = True
    except Exception as exc:
        response["error"] = _safe_error(exc)
    return response


def persist_backtest_result(result: dict, source: str = "api") -> None:
    if not analytics_enabled() or not isinstance(result, dict):
        return

    try:
        request = result.get("_analytics_request") if isinstance(result.get("_analytics_request"), dict) else {}
        public_request = result.get("request") if isinstance(result.get("request"), dict) else {}
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        mcp = diagnostics.get("mcp") if isinstance(diagnostics.get("mcp"), dict) else {}
        data_quality = mcp.get("data_quality") if isinstance(mcp.get("data_quality"), dict) else diagnostics
        monte_carlo = request.get("monte_carlo") if isinstance(request.get("monte_carlo"), dict) else {}
        symbol = safe_str(public_request.get("symbol") or request.get("symbol"), 32)
        strategy = safe_str(public_request.get("strategy") or request.get("strategy"), 128)
        run_id = (
            safe_str(result.get("run_id"), 128)
            or safe_str(request.get("run_id"), 128)
            or safe_str(mcp.get("run_id"), 128)
            or f"bt_{uuid.uuid4().hex[:12]}"
        )

        row = {
            "run_id": run_id,
            "source": safe_str(source, 64),
            "status": safe_str(result.get("status") or "success", 32),
            "error_message": safe_str(_first_item(result.get("errors")) or result.get("message"), 2048)
            if result.get("status") == "error"
            else None,
            "request_type": safe_str(request.get("request_type") or "strategy_backtest", 64),
            "symbol": symbol,
            "strategy": strategy,
            "lookback": safe_str(request.get("lookback"), 32),
            "resolution": safe_str(request.get("resolution"), 16),
            "initial_cash": safe_float(request.get("initial_cash")),
            "fees": safe_float(request.get("fees")),
            "total_return_pct": safe_float(metrics.get("total_return_pct")),
            "buy_hold_return_pct": safe_float(metrics.get("buy_hold_return_pct")),
            "alpha_vs_buy_hold_pct": safe_float(metrics.get("alpha_vs_buy_hold_pct")),
            "sharpe_ratio": safe_float(metrics.get("sharpe_ratio")),
            "max_drawdown_pct": safe_float(metrics.get("max_drawdown_pct")),
            "win_rate_pct": safe_float(metrics.get("win_rate_pct")),
            "total_trades": safe_int(metrics.get("total_trades")),
            "final_value": safe_float(metrics.get("final_value")),
            "monte_carlo_days": safe_int(monte_carlo.get("days")),
            "monte_carlo_simulations": safe_int(monte_carlo.get("simulations")),
            "mc_expected_return_pct": safe_float(
                summary.get("monte_carlo_expected_return_pct") or summary.get("expected_return_pct")
            ),
            "mc_probability_positive_pct": safe_float(summary.get("probability_positive_return_pct")),
            "mc_p5_return_pct": safe_float(summary.get("p5_return_pct")),
            "mc_p95_return_pct": safe_float(summary.get("p95_return_pct")),
            "mcp_tool": safe_str(mcp.get("tool"), 128),
            "mcp_transport": safe_str(mcp.get("transport"), 64),
            "mcp_server_url": safe_str(mcp.get("server_url")),
            "cache_status": safe_str(data_quality.get("cache_status"), 32) if isinstance(data_quality, dict) else None,
            "candles_fetched": safe_int(data_quality.get("candles_fetched")) if isinstance(data_quality, dict) else None,
            "request_json": _jsonb(request or public_request),
            "metrics_json": _jsonb(metrics),
            "summary_json": _jsonb(summary),
            "diagnostics_json": _jsonb(diagnostics),
        }

        parameters = public_request.get("parameters") or request.get("parameters") or {}
        trades = ((result.get("tables") or {}).get("trades") or []) if isinstance(result.get("tables"), dict) else []
        charts = result.get("charts") if isinstance(result.get("charts"), dict) else {}

        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_BACKTEST_RUN_UPSERT_SQL, _backtest_row_values(row))
                cursor.execute("DELETE FROM backtest_parameters WHERE run_id = %s", (run_id,))
                parameter_rows = list(_parameter_rows(run_id, parameters))
                if parameter_rows:
                    cursor.executemany(
                        """
                        INSERT INTO backtest_parameters (run_id, parameter_name, parameter_value)
                        VALUES (%s, %s, %s)
                        """,
                        parameter_rows,
                    )
                cursor.execute("DELETE FROM backtest_trades WHERE run_id = %s", (run_id,))
                trade_rows = list(_trade_rows(run_id, symbol, strategy, trades))
                if trade_rows:
                    cursor.executemany(
                        """
                        INSERT INTO backtest_trades (
                            run_id, symbol, strategy, entry_time, exit_time, side,
                            entry_price, exit_price, pnl, return_pct, duration_days, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        trade_rows,
                    )
                cursor.execute("DELETE FROM equity_points WHERE run_id = %s", (run_id,))
                equity_rows = list(_equity_rows(run_id, charts))
                if equity_rows:
                    cursor.executemany(
                        """
                        INSERT INTO equity_points (
                            run_id, time, strategy_equity, buy_hold_equity, spy_equity, drawdown_pct
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        equity_rows,
                    )
    except Exception as exc:
        logger.warning("Analytics backtest persistence failed: %s", _safe_error(exc))


def persist_portfolio_optimization_result(result: dict, source: str = "api") -> None:
    if not analytics_enabled() or not isinstance(result, dict):
        return

    try:
        request = result.get("_analytics_request") if isinstance(result.get("_analytics_request"), dict) else {}
        portfolio_result = result.get("portfolio_result") if isinstance(result.get("portfolio_result"), dict) else result
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        mcp = diagnostics.get("mcp") if isinstance(diagnostics.get("mcp"), dict) else {}
        metrics = portfolio_result.get("metrics") if isinstance(portfolio_result.get("metrics"), dict) else {}
        charts = portfolio_result.get("charts") if isinstance(portfolio_result.get("charts"), dict) else {}
        min_vol = _portfolio_point(charts.get("min_volatility_portfolio"))
        max_sharpe = _portfolio_point(charts.get("max_sharpe_portfolio"))
        weights = portfolio_result.get("weights") if isinstance(portfolio_result.get("weights"), dict) else {}
        symbols_requested = request.get("symbols") if isinstance(request.get("symbols"), list) else []
        symbols_used = portfolio_result.get("symbols_used") or portfolio_result.get("symbols")
        symbols_used_count = len(symbols_used) if isinstance(symbols_used, list) else None
        run_id = (
            safe_str(result.get("run_id"), 128)
            or safe_str(request.get("run_id"), 128)
            or safe_str(portfolio_result.get("artifact_id"), 128)
            or safe_str(mcp.get("artifact_id"), 128)
            or f"po_{uuid.uuid4().hex[:12]}"
        )

        row = {
            "run_id": run_id,
            "status": safe_str(result.get("status") or portfolio_result.get("status") or "success", 32),
            "error_message": safe_str(_first_item(result.get("errors")) or result.get("message"), 2048)
            if result.get("status") == "error"
            else None,
            "objective": safe_str(portfolio_result.get("objective") or request.get("objective"), 64),
            "selection_mode": safe_str(portfolio_result.get("selection_mode"), 64),
            "sector": safe_str(portfolio_result.get("sector") or request.get("sector"), 128),
            "symbols_requested": len(symbols_requested) if symbols_requested else None,
            "symbols_used": symbols_used_count,
            "lookback": safe_str(request.get("lookback"), 32),
            "resolution": safe_str(request.get("resolution"), 16),
            "risk_free_rate": safe_float(request.get("risk_free_rate")),
            "allow_short": request.get("allow_short") if isinstance(request.get("allow_short"), bool) else None,
            "max_weight": safe_float(request.get("max_weight")),
            "num_frontier_portfolios": safe_int(request.get("num_frontier_portfolios")),
            "expected_annual_return_pct": safe_float(metrics.get("expected_annual_return_pct")),
            "annual_volatility_pct": safe_float(metrics.get("annual_volatility_pct")),
            "sharpe_ratio": safe_float(metrics.get("sharpe_ratio")),
            "min_vol_return_pct": _portfolio_return_pct(min_vol),
            "min_vol_volatility_pct": _portfolio_volatility_pct(min_vol),
            "min_vol_sharpe_ratio": safe_float(min_vol.get("sharpe_ratio")),
            "max_sharpe_return_pct": _portfolio_return_pct(max_sharpe),
            "max_sharpe_volatility_pct": _portfolio_volatility_pct(max_sharpe),
            "max_sharpe_ratio": safe_float(max_sharpe.get("sharpe_ratio")),
            "artifact_url": safe_str(portfolio_result.get("artifact_url") or mcp.get("artifact_url")),
            "mcp_tool": safe_str(mcp.get("tool"), 128),
            "mcp_transport": safe_str(mcp.get("transport"), 64),
            "mcp_server_url": safe_str(mcp.get("server_url")),
            "request_json": _jsonb(request),
            "result_json": _jsonb(_compact_portfolio_result(portfolio_result)),
            "diagnostics_json": _jsonb(diagnostics),
        }

        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_PORTFOLIO_RUN_UPSERT_SQL, _portfolio_row_values(row))
                cursor.execute("DELETE FROM portfolio_weights WHERE run_id = %s", (run_id,))
                weight_rows = list(_portfolio_weight_rows(run_id, weights))
                if weight_rows:
                    cursor.executemany(
                        """
                        INSERT INTO portfolio_weights (run_id, ticker, company_name, sector, weight)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        weight_rows,
                    )
    except Exception as exc:
        logger.warning("Analytics portfolio persistence failed: %s", _safe_error(exc))


def persist_factor_portfolio_result(result: dict, source: str = "api") -> None:
    if not analytics_enabled() or not isinstance(result, dict):
        return

    try:
        request = result.get("_analytics_request") if isinstance(result.get("_analytics_request"), dict) else {}
        factor_result = result.get("factor_portfolio_result") if isinstance(result.get("factor_portfolio_result"), dict) else result
        universe = factor_result.get("universe_summary") if isinstance(factor_result.get("universe_summary"), dict) else {}
        config = factor_result.get("factor_model_configuration") if isinstance(factor_result.get("factor_model_configuration"), dict) else {}
        optimization = factor_result.get("optimization_result") if isinstance(factor_result.get("optimization_result"), dict) else {}
        metrics = optimization.get("metrics") if isinstance(optimization.get("metrics"), dict) else {}
        scenario = factor_result.get("scenario_analysis") if isinstance(factor_result.get("scenario_analysis"), dict) else {}
        scenario_summary = {
            "config": {
                "days": scenario.get("days"),
                "simulations": scenario.get("simulations"),
                "block_size": scenario.get("block_size"),
                "seed": scenario.get("seed"),
            },
            "scenarios": scenario.get("scenarios") if isinstance(scenario.get("scenarios"), list) else [],
        }
        run_id = (
            safe_str(result.get("run_id"), 128)
            or safe_str(factor_result.get("run_id"), 128)
            or safe_str(factor_result.get("artifact_id"), 128)
            or f"fp_{uuid.uuid4().hex[:12]}"
        )
        selected = factor_result.get("selected_stocks") if isinstance(factor_result.get("selected_stocks"), list) else []
        scores = factor_result.get("factor_scores") if isinstance(factor_result.get("factor_scores"), list) else []
        row = {
            "run_id": run_id,
            "status": safe_str(result.get("status") or factor_result.get("status") or "success", 32),
            "selection_mode": safe_str(request.get("selection_mode") or (factor_result.get("request_summary") or {}).get("selection_mode"), 64),
            "sector": safe_str(request.get("sector") or (factor_result.get("request_summary") or {}).get("sector"), 128),
            "symbols_requested": safe_int(universe.get("symbols_requested")),
            "symbols_scored": safe_int(universe.get("symbols_scored")),
            "symbols_selected": safe_int(universe.get("symbols_selected")),
            "factor_configuration": _jsonb(config),
            "normalization_mode": safe_str(config.get("normalization_mode"), 64),
            "selection_method": safe_str(config.get("selection_method"), 64),
            "top_n": safe_int(config.get("top_n")),
            "minimum_score": safe_float(config.get("minimum_score")),
            "minimum_data_coverage_pct": safe_float(config.get("minimum_data_coverage_pct")),
            "optimization_objective": safe_str(optimization.get("objective") or (request.get("optimization") or {}).get("objective"), 64),
            "expected_return_method": safe_str((request.get("optimization") or {}).get("expected_return_method"), 64),
            "expected_annual_return_pct": safe_float(metrics.get("expected_annual_return_pct")),
            "annual_volatility_pct": safe_float(metrics.get("annual_volatility_pct")),
            "sharpe_ratio": safe_float(metrics.get("sharpe_ratio")),
            "scenario_summary": _jsonb(scenario_summary),
            "warnings": _jsonb(factor_result.get("warnings") if isinstance(factor_result.get("warnings"), list) else []),
            "runtime_ms": None,
        }

        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_FACTOR_PORTFOLIO_RUN_UPSERT_SQL, _factor_portfolio_row_values(row))
                cursor.execute("DELETE FROM stock_factor_scores WHERE run_id = %s", (run_id,))
                score_rows = list(_stock_factor_score_rows(run_id, scores, selected))
                if score_rows:
                    cursor.executemany(
                        """
                        INSERT INTO stock_factor_scores (
                            run_id, ticker, company_name, sector,
                            fundamental_quality_score, valuation_score, momentum_score,
                            analyst_score, financial_risk_score, quantitative_alpha_score,
                            combined_portfolio_score, data_coverage_pct, selection_status,
                            selection_reason, expected_return_original, expected_return_adjusted,
                            final_portfolio_weight, raw_values_json, normalized_scores_json,
                            effective_weights_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        score_rows,
                    )
    except Exception as exc:
        logger.warning("Analytics factor portfolio persistence failed: %s", _safe_error(exc))


def persist_mcp_tool_call(event: dict) -> None:
    if not analytics_enabled() or not isinstance(event, dict):
        return

    try:
        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO mcp_tool_calls (
                        request_id, tool_name, transport, server_url, status, runtime_ms,
                        error_message, request_type, symbol, strategy, sector, symbols_count
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        safe_str(event.get("request_id"), 128),
                        safe_str(event.get("tool_name"), 128),
                        safe_str(event.get("transport"), 64),
                        safe_str(event.get("server_url")),
                        safe_str(event.get("status"), 32),
                        safe_int(event.get("runtime_ms")),
                        safe_str(event.get("error_message"), 2048),
                        safe_str(event.get("request_type"), 64),
                        safe_str(event.get("symbol"), 32),
                        safe_str(event.get("strategy"), 128),
                        safe_str(event.get("sector"), 128),
                        safe_int(event.get("symbols_count")),
                    ),
                )
    except Exception as exc:
        logger.warning("Analytics MCP call persistence failed: %s", _safe_error(exc))


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def safe_str(value: Any, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length] if max_length else text


def redact_sensitive_fields(data: Any) -> Any:
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_sensitive_fields(value)
        return redacted
    if isinstance(data, list):
        return [redact_sensitive_fields(item) for item in data]
    if isinstance(data, tuple):
        return [redact_sensitive_fields(item) for item in data]
    return _json_ready(data)


def _jsonb(value: Any):
    from psycopg.types.json import Jsonb

    return Jsonb(redact_sensitive_fields(value or {}))


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower())
    return any(marker in normalized for marker in SENSITIVE_FIELD_MARKERS)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        try:
            return _json_ready(value.item())
        except Exception:
            pass
    return str(value)


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    for marker in SENSITIVE_FIELD_MARKERS:
        message = re.sub(
            rf"({marker}\s*[=:]\s*)[^\s,;]+",
            rf"\1[REDACTED]",
            message,
            flags=re.IGNORECASE,
        )
    return message[:2048]


def _backtest_row_values(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[column] for column in _BACKTEST_COLUMNS)


def _portfolio_row_values(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[column] for column in _PORTFOLIO_COLUMNS)


def _factor_portfolio_row_values(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[column] for column in _FACTOR_PORTFOLIO_COLUMNS)


def _parameter_rows(run_id: str, parameters: Any):
    if not isinstance(parameters, dict):
        return
    for key, value in parameters.items():
        yield (run_id, safe_str(key, 128), safe_str(_parameter_value(value), 256))


def _parameter_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(redact_sensitive_fields(value), sort_keys=True)
    return "" if value is None else str(value)


def _trade_rows(run_id: str, symbol: str | None, strategy: str | None, trades: Any):
    if not isinstance(trades, list):
        return
    for trade in trades[:1000]:
        if not isinstance(trade, dict):
            continue
        yield (
            run_id,
            symbol,
            strategy,
            _safe_datetime(_pick(trade, "entry_time", "entry_timestamp", "entry_date")),
            _safe_datetime(_pick(trade, "exit_time", "exit_timestamp", "exit_date")),
            safe_str(_pick(trade, "side", "direction"), 32),
            safe_float(_pick(trade, "entry_price", "avg_entry_price")),
            safe_float(_pick(trade, "exit_price", "avg_exit_price")),
            safe_float(_pick(trade, "pnl")),
            _safe_pct(_pick(trade, "return_pct", "return")),
            _duration_days(_pick(trade, "duration_days", "duration")),
            safe_str(_pick(trade, "status"), 32),
        )


def _equity_rows(run_id: str, charts: dict[str, Any]):
    equity_curve = charts.get("equity_curve") if isinstance(charts, dict) else []
    drawdown_curve = charts.get("drawdown_curve") if isinstance(charts, dict) else []
    drawdown_by_time = {
        _time_key(point): safe_float(_pick(point, "drawdown_pct", "value"))
        for point in drawdown_curve
        if isinstance(point, dict) and _time_key(point)
    } if isinstance(drawdown_curve, list) else {}

    if not isinstance(equity_curve, list):
        return
    for point in equity_curve[:5000]:
        if not isinstance(point, dict):
            continue
        key = _time_key(point)
        if not key:
            continue
        yield (
            run_id,
            _safe_datetime(key),
            safe_float(_pick(point, "strategy_equity", "strategy", "value")),
            safe_float(_pick(point, "buy_hold_equity", "buy_hold")),
            safe_float(_pick(point, "spy_equity", "spy")),
            safe_float(_pick(point, "drawdown_pct")) or drawdown_by_time.get(key),
        )


def _portfolio_weight_rows(run_id: str, weights: dict[str, Any]):
    for ticker, weight in sorted(weights.items()):
        yield (run_id, safe_str(ticker, 32), None, None, safe_float(weight))


def _stock_factor_score_rows(run_id: str, scores: list[Any], selected: list[Any]):
    selected_by_ticker = {
        safe_str(item.get("ticker"), 32): item
        for item in selected
        if isinstance(item, dict) and safe_str(item.get("ticker"), 32)
    }
    for item in scores:
        if not isinstance(item, dict):
            continue
        ticker = safe_str(item.get("ticker"), 32)
        detail = selected_by_ticker.get(ticker, item) if ticker else item
        yield (
            run_id,
            ticker,
            safe_str(item.get("company_name"), 256),
            safe_str(item.get("sector"), 128),
            safe_float(item.get("fundamental_quality_score")),
            safe_float(item.get("valuation_score")),
            safe_float(item.get("momentum_score")),
            safe_float(item.get("analyst_score")),
            safe_float(item.get("financial_risk_score")),
            safe_float(item.get("quantitative_alpha_score")),
            safe_float(item.get("combined_portfolio_score")),
            safe_float(item.get("data_coverage_pct")),
            safe_str(item.get("selection_status"), 32),
            safe_str(item.get("selection_reason"), 512),
            safe_float(item.get("expected_return_original")),
            safe_float(item.get("expected_return_adjusted")),
            safe_float(item.get("final_portfolio_weight")),
            _jsonb(detail.get("raw_factor_values") if isinstance(detail.get("raw_factor_values"), dict) else {}),
            _jsonb(detail.get("normalized_factor_scores") if isinstance(detail.get("normalized_factor_scores"), dict) else {}),
            _jsonb(detail.get("effective_factor_weights") if isinstance(detail.get("effective_factor_weights"), dict) else {}),
        )


def _compact_portfolio_result(portfolio_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": portfolio_result.get("status"),
        "objective": portfolio_result.get("objective"),
        "symbols": portfolio_result.get("symbols"),
        "selection_mode": portfolio_result.get("selection_mode"),
        "sector": portfolio_result.get("sector"),
        "symbols_used": portfolio_result.get("symbols_used"),
        "rejected_symbols": portfolio_result.get("rejected_symbols"),
        "weights": portfolio_result.get("weights"),
        "metrics": portfolio_result.get("metrics"),
        "data_quality": portfolio_result.get("data_quality"),
        "artifact_id": portfolio_result.get("artifact_id"),
        "artifact_url": portfolio_result.get("artifact_url"),
        "scenario_analysis": portfolio_result.get("scenario_analysis"),
        "warnings": portfolio_result.get("warnings"),
    }


def _portfolio_point(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _portfolio_return_pct(point: dict[str, Any]) -> float | None:
    explicit = safe_float(point.get("expected_annual_return_pct"))
    if explicit is not None:
        return explicit
    raw = safe_float(point.get("portfolio_return"))
    return raw * 100.0 if raw is not None else None


def _portfolio_volatility_pct(point: dict[str, Any]) -> float | None:
    explicit = safe_float(point.get("annual_volatility_pct"))
    if explicit is not None:
        return explicit
    raw = safe_float(point.get("portfolio_volatility"))
    return raw * 100.0 if raw is not None else None


def _safe_pct(value: Any) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    return parsed * 100.0 if -1.0 <= parsed <= 1.0 else parsed


def _duration_days(value: Any) -> int | None:
    parsed = safe_int(value)
    if parsed is not None:
        return parsed
    text = safe_str(value)
    if not text:
        return None
    match = re.search(r"(-?\d+)\s+days?", text, flags=re.IGNORECASE)
    return safe_int(match.group(1)) if match else None


def _safe_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _time_key(point: dict[str, Any]) -> str | None:
    return safe_str(point.get("time") or point.get("date"))


def _pick(mapping: dict[str, Any], *keys: str) -> Any:
    normalized = {_normalize_key(key): value for key, value in mapping.items()}
    for key in keys:
        value = normalized.get(_normalize_key(key))
        if value is not None:
            return value
    return None


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def _first_item(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value


_BACKTEST_COLUMNS = (
    "run_id",
    "source",
    "status",
    "error_message",
    "request_type",
    "symbol",
    "strategy",
    "lookback",
    "resolution",
    "initial_cash",
    "fees",
    "total_return_pct",
    "buy_hold_return_pct",
    "alpha_vs_buy_hold_pct",
    "sharpe_ratio",
    "max_drawdown_pct",
    "win_rate_pct",
    "total_trades",
    "final_value",
    "monte_carlo_days",
    "monte_carlo_simulations",
    "mc_expected_return_pct",
    "mc_probability_positive_pct",
    "mc_p5_return_pct",
    "mc_p95_return_pct",
    "mcp_tool",
    "mcp_transport",
    "mcp_server_url",
    "cache_status",
    "candles_fetched",
    "request_json",
    "metrics_json",
    "summary_json",
    "diagnostics_json",
)

_BACKTEST_RUN_UPSERT_SQL = f"""
INSERT INTO backtest_runs ({", ".join(_BACKTEST_COLUMNS)})
VALUES ({", ".join(["%s"] * len(_BACKTEST_COLUMNS))})
ON CONFLICT (run_id) DO UPDATE SET
    source = EXCLUDED.source,
    status = EXCLUDED.status,
    error_message = EXCLUDED.error_message,
    request_type = EXCLUDED.request_type,
    symbol = EXCLUDED.symbol,
    strategy = EXCLUDED.strategy,
    lookback = EXCLUDED.lookback,
    resolution = EXCLUDED.resolution,
    initial_cash = EXCLUDED.initial_cash,
    fees = EXCLUDED.fees,
    total_return_pct = EXCLUDED.total_return_pct,
    buy_hold_return_pct = EXCLUDED.buy_hold_return_pct,
    alpha_vs_buy_hold_pct = EXCLUDED.alpha_vs_buy_hold_pct,
    sharpe_ratio = EXCLUDED.sharpe_ratio,
    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
    win_rate_pct = EXCLUDED.win_rate_pct,
    total_trades = EXCLUDED.total_trades,
    final_value = EXCLUDED.final_value,
    monte_carlo_days = EXCLUDED.monte_carlo_days,
    monte_carlo_simulations = EXCLUDED.monte_carlo_simulations,
    mc_expected_return_pct = EXCLUDED.mc_expected_return_pct,
    mc_probability_positive_pct = EXCLUDED.mc_probability_positive_pct,
    mc_p5_return_pct = EXCLUDED.mc_p5_return_pct,
    mc_p95_return_pct = EXCLUDED.mc_p95_return_pct,
    mcp_tool = EXCLUDED.mcp_tool,
    mcp_transport = EXCLUDED.mcp_transport,
    mcp_server_url = EXCLUDED.mcp_server_url,
    cache_status = EXCLUDED.cache_status,
    candles_fetched = EXCLUDED.candles_fetched,
    request_json = EXCLUDED.request_json,
    metrics_json = EXCLUDED.metrics_json,
    summary_json = EXCLUDED.summary_json,
    diagnostics_json = EXCLUDED.diagnostics_json
"""

_PORTFOLIO_COLUMNS = (
    "run_id",
    "status",
    "error_message",
    "objective",
    "selection_mode",
    "sector",
    "symbols_requested",
    "symbols_used",
    "lookback",
    "resolution",
    "risk_free_rate",
    "allow_short",
    "max_weight",
    "num_frontier_portfolios",
    "expected_annual_return_pct",
    "annual_volatility_pct",
    "sharpe_ratio",
    "min_vol_return_pct",
    "min_vol_volatility_pct",
    "min_vol_sharpe_ratio",
    "max_sharpe_return_pct",
    "max_sharpe_volatility_pct",
    "max_sharpe_ratio",
    "artifact_url",
    "mcp_tool",
    "mcp_transport",
    "mcp_server_url",
    "request_json",
    "result_json",
    "diagnostics_json",
)

_PORTFOLIO_RUN_UPSERT_SQL = f"""
INSERT INTO portfolio_optimization_runs ({", ".join(_PORTFOLIO_COLUMNS)})
VALUES ({", ".join(["%s"] * len(_PORTFOLIO_COLUMNS))})
ON CONFLICT (run_id) DO UPDATE SET
    status = EXCLUDED.status,
    error_message = EXCLUDED.error_message,
    objective = EXCLUDED.objective,
    selection_mode = EXCLUDED.selection_mode,
    sector = EXCLUDED.sector,
    symbols_requested = EXCLUDED.symbols_requested,
    symbols_used = EXCLUDED.symbols_used,
    lookback = EXCLUDED.lookback,
    resolution = EXCLUDED.resolution,
    risk_free_rate = EXCLUDED.risk_free_rate,
    allow_short = EXCLUDED.allow_short,
    max_weight = EXCLUDED.max_weight,
    num_frontier_portfolios = EXCLUDED.num_frontier_portfolios,
    expected_annual_return_pct = EXCLUDED.expected_annual_return_pct,
    annual_volatility_pct = EXCLUDED.annual_volatility_pct,
    sharpe_ratio = EXCLUDED.sharpe_ratio,
    min_vol_return_pct = EXCLUDED.min_vol_return_pct,
    min_vol_volatility_pct = EXCLUDED.min_vol_volatility_pct,
    min_vol_sharpe_ratio = EXCLUDED.min_vol_sharpe_ratio,
    max_sharpe_return_pct = EXCLUDED.max_sharpe_return_pct,
    max_sharpe_volatility_pct = EXCLUDED.max_sharpe_volatility_pct,
    max_sharpe_ratio = EXCLUDED.max_sharpe_ratio,
    artifact_url = EXCLUDED.artifact_url,
    mcp_tool = EXCLUDED.mcp_tool,
    mcp_transport = EXCLUDED.mcp_transport,
    mcp_server_url = EXCLUDED.mcp_server_url,
    request_json = EXCLUDED.request_json,
    result_json = EXCLUDED.result_json,
    diagnostics_json = EXCLUDED.diagnostics_json
"""

_FACTOR_PORTFOLIO_COLUMNS = (
    "run_id",
    "status",
    "selection_mode",
    "sector",
    "symbols_requested",
    "symbols_scored",
    "symbols_selected",
    "factor_configuration",
    "normalization_mode",
    "selection_method",
    "top_n",
    "minimum_score",
    "minimum_data_coverage_pct",
    "optimization_objective",
    "expected_return_method",
    "expected_annual_return_pct",
    "annual_volatility_pct",
    "sharpe_ratio",
    "scenario_summary",
    "warnings",
    "runtime_ms",
)

_FACTOR_PORTFOLIO_RUN_UPSERT_SQL = f"""
INSERT INTO factor_portfolio_runs ({", ".join(_FACTOR_PORTFOLIO_COLUMNS)})
VALUES ({", ".join(["%s"] * len(_FACTOR_PORTFOLIO_COLUMNS))})
ON CONFLICT (run_id) DO UPDATE SET
    status = EXCLUDED.status,
    selection_mode = EXCLUDED.selection_mode,
    sector = EXCLUDED.sector,
    symbols_requested = EXCLUDED.symbols_requested,
    symbols_scored = EXCLUDED.symbols_scored,
    symbols_selected = EXCLUDED.symbols_selected,
    factor_configuration = EXCLUDED.factor_configuration,
    normalization_mode = EXCLUDED.normalization_mode,
    selection_method = EXCLUDED.selection_method,
    top_n = EXCLUDED.top_n,
    minimum_score = EXCLUDED.minimum_score,
    minimum_data_coverage_pct = EXCLUDED.minimum_data_coverage_pct,
    optimization_objective = EXCLUDED.optimization_objective,
    expected_return_method = EXCLUDED.expected_return_method,
    expected_annual_return_pct = EXCLUDED.expected_annual_return_pct,
    annual_volatility_pct = EXCLUDED.annual_volatility_pct,
    sharpe_ratio = EXCLUDED.sharpe_ratio,
    scenario_summary = EXCLUDED.scenario_summary,
    warnings = EXCLUDED.warnings,
    runtime_ms = EXCLUDED.runtime_ms
"""
