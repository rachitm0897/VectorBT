import json
import logging
import math
import os
import re
import uuid
from datetime import date, datetime, timedelta
from threading import Thread
from typing import Any

try:
    import psycopg
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover - dependency is installed in the backend image.
    psycopg = None
    Json = None


logger = logging.getLogger(__name__)


def analytics_enabled() -> bool:
    value = os.getenv("ANALYTICS_ENABLED", "true").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def get_analytics_connection():
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Install backend requirements before using analytics.")

    timeout = safe_int(os.getenv("ANALYTICS_DB_CONNECT_TIMEOUT")) or 2
    return psycopg.connect(
        dbname=os.getenv("ANALYTICS_DB_NAME", "analytics"),
        user=os.getenv("ANALYTICS_DB_USER", "analytics_user"),
        password=os.getenv("ANALYTICS_DB_PASSWORD", "analytics_password"),
        host=os.getenv("ANALYTICS_DB_HOST", "localhost"),
        port=safe_int(os.getenv("ANALYTICS_DB_PORT")) or 5433,
        connect_timeout=timeout,
    )


def persist_backtest_analytics(result: dict, source: str = "api") -> None:
    if not analytics_enabled():
        return

    try:
        payload = _extract_payload(result, source)
        with get_analytics_connection() as connection:
            with connection.cursor() as cursor:
                _upsert_run(cursor, payload)
                _replace_parameters(cursor, payload)
                _replace_trades(cursor, payload)
                _replace_equity_points(cursor, payload)
    except Exception:
        logger.exception("Analytics persistence failed")


def persist_backtest_analytics_async(result: dict, source: str = "api") -> None:
    if not analytics_enabled():
        return

    try:
        Thread(
            target=persist_backtest_analytics,
            args=(result, source),
            daemon=True,
        ).start()
    except Exception:
        logger.exception("Could not start analytics persistence worker")


def safe_float(value: Any):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def safe_int(value: Any):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed


def safe_str(value: Any, max_length: int | None = None):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length] if max_length else text


def _extract_payload(result: dict, source: str) -> dict:
    analytics_request = result.get("_analytics_request")
    request = analytics_request if isinstance(analytics_request, dict) else result.get("request") or {}
    metrics = result.get("metrics") or {}
    summary = result.get("summary") or {}
    diagnostics = result.get("diagnostics") or {}
    charts = result.get("charts") or {}
    tables = result.get("tables") or {}
    monte_carlo = request.get("monte_carlo") if isinstance(request.get("monte_carlo"), dict) else {}

    status = safe_str(result.get("status"), 32) or "unknown"
    run_id = safe_str(
        result.get("run_id")
        or result.get("result_id")
        or diagnostics.get("run_id")
        or uuid.uuid4().hex,
        64,
    )

    return {
        "run_id": run_id,
        "source": safe_str(source, 32),
        "status": status,
        "error_message": None if status == "success" else safe_str(result.get("message")),
        "symbol": safe_str(request.get("symbol"), 20),
        "strategy": safe_str(request.get("strategy"), 64),
        "lookback": safe_str(request.get("lookback"), 20),
        "resolution": safe_str(request.get("resolution"), 10),
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
        "mc_expected_return_pct": _first_float(
            summary,
            "mc_expected_return_pct",
            "monte_carlo_expected_return_pct",
        ),
        "mc_probability_positive_pct": _first_float(
            summary,
            "mc_probability_positive_pct",
            "probability_positive_return_pct",
        ),
        "mc_p5_return_pct": _first_float(summary, "mc_p5_return_pct", "p5_return_pct"),
        "mc_p95_return_pct": _first_float(summary, "mc_p95_return_pct", "p95_return_pct"),
        "llm_calls": safe_int(diagnostics.get("llm_calls")),
        "parser_cache": safe_str(diagnostics.get("parser_cache"), 20),
        "estimated_prompt_tokens": safe_int(diagnostics.get("estimated_prompt_tokens")),
        "estimated_output_tokens": safe_int(diagnostics.get("estimated_output_tokens")),
        "cache_status": safe_str(diagnostics.get("cache_status"), 20),
        "candles_fetched": safe_int(diagnostics.get("candles_fetched")) or _chart_length(charts.get("price")),
        "request_json": _json_safe(request),
        "metrics_json": _json_safe(metrics),
        "summary_json": _json_safe(summary),
        "diagnostics_json": _json_safe(diagnostics),
        "parameters": request.get("parameters") if isinstance(request.get("parameters"), dict) else {},
        "trades": tables.get("trades") if isinstance(tables.get("trades"), list) else [],
        "equity_curve": charts.get("equity_curve") if isinstance(charts.get("equity_curve"), list) else [],
        "drawdown_curve": charts.get("drawdown_curve") if isinstance(charts.get("drawdown_curve"), list) else [],
    }


def _upsert_run(cursor, payload: dict) -> None:
    cursor.execute(
        """
        INSERT INTO backtest_runs (
            run_id, source, status, error_message, symbol, strategy, lookback, resolution,
            initial_cash, fees, total_return_pct, buy_hold_return_pct, alpha_vs_buy_hold_pct,
            sharpe_ratio, max_drawdown_pct, win_rate_pct, total_trades, final_value,
            monte_carlo_days, monte_carlo_simulations, mc_expected_return_pct,
            mc_probability_positive_pct, mc_p5_return_pct, mc_p95_return_pct, llm_calls,
            parser_cache, estimated_prompt_tokens, estimated_output_tokens, cache_status,
            candles_fetched, request_json, metrics_json, summary_json, diagnostics_json
        )
        VALUES (
            %(run_id)s, %(source)s, %(status)s, %(error_message)s, %(symbol)s, %(strategy)s,
            %(lookback)s, %(resolution)s, %(initial_cash)s, %(fees)s, %(total_return_pct)s,
            %(buy_hold_return_pct)s, %(alpha_vs_buy_hold_pct)s, %(sharpe_ratio)s,
            %(max_drawdown_pct)s, %(win_rate_pct)s, %(total_trades)s, %(final_value)s,
            %(monte_carlo_days)s, %(monte_carlo_simulations)s, %(mc_expected_return_pct)s,
            %(mc_probability_positive_pct)s, %(mc_p5_return_pct)s, %(mc_p95_return_pct)s,
            %(llm_calls)s, %(parser_cache)s, %(estimated_prompt_tokens)s,
            %(estimated_output_tokens)s, %(cache_status)s, %(candles_fetched)s,
            %(request_json)s, %(metrics_json)s, %(summary_json)s, %(diagnostics_json)s
        )
        ON CONFLICT (run_id) DO UPDATE SET
            source = EXCLUDED.source,
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message,
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
            llm_calls = EXCLUDED.llm_calls,
            parser_cache = EXCLUDED.parser_cache,
            estimated_prompt_tokens = EXCLUDED.estimated_prompt_tokens,
            estimated_output_tokens = EXCLUDED.estimated_output_tokens,
            cache_status = EXCLUDED.cache_status,
            candles_fetched = EXCLUDED.candles_fetched,
            request_json = EXCLUDED.request_json,
            metrics_json = EXCLUDED.metrics_json,
            summary_json = EXCLUDED.summary_json,
            diagnostics_json = EXCLUDED.diagnostics_json
        """,
        _db_payload(payload),
    )


def _replace_parameters(cursor, payload: dict) -> None:
    cursor.execute("DELETE FROM backtest_parameters WHERE run_id = %s", (payload["run_id"],))
    for name, value in sorted(payload["parameters"].items()):
        cursor.execute(
            """
            INSERT INTO backtest_parameters (run_id, parameter_name, parameter_value)
            VALUES (%s, %s, %s)
            """,
            (
                payload["run_id"],
                safe_str(name, 64),
                safe_str(_compact_value(value), 128),
            ),
        )


def _replace_trades(cursor, payload: dict) -> None:
    cursor.execute("DELETE FROM backtest_trades WHERE run_id = %s", (payload["run_id"],))
    for trade in payload["trades"][:500]:
        if not isinstance(trade, dict):
            continue
        return_value = _first_value(trade, "return_pct", "return", "return_percent")
        return_pct = safe_float(return_value)
        if return_pct is not None and "return_pct" not in trade and abs(return_pct) <= 1:
            return_pct *= 100

        cursor.execute(
            """
            INSERT INTO backtest_trades (
                run_id, symbol, strategy, entry_time, exit_time, side, entry_price,
                exit_price, pnl, return_pct, duration_days, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload["run_id"],
                payload["symbol"],
                payload["strategy"],
                _safe_timestamp(_first_value(trade, "entry_time", "entry_timestamp", "entry_date")),
                _safe_timestamp(_first_value(trade, "exit_time", "exit_timestamp", "exit_date")),
                safe_str(_first_value(trade, "side", "direction"), 16),
                _first_float(trade, "entry_price", "avg_entry_price"),
                _first_float(trade, "exit_price", "avg_exit_price"),
                _first_float(trade, "pnl", "profit_loss"),
                return_pct,
                _safe_duration_days(_first_value(trade, "duration_days", "duration")),
                safe_str(_first_value(trade, "status"), 32),
            ),
        )


def _replace_equity_points(cursor, payload: dict) -> None:
    cursor.execute("DELETE FROM equity_points WHERE run_id = %s", (payload["run_id"],))
    drawdowns = {
        _time_key(point): safe_float(point.get("drawdown_pct"))
        for point in payload["drawdown_curve"]
        if isinstance(point, dict)
    }
    for point in payload["equity_curve"][:2000]:
        if not isinstance(point, dict):
            continue
        time_value = _first_value(point, "time", "date")
        drawdown = _first_float(point, "drawdown_pct")
        if drawdown is None:
            drawdown = drawdowns.get(_time_key(point))

        cursor.execute(
            """
            INSERT INTO equity_points (
                run_id, time, strategy_equity, buy_hold_equity, spy_equity, drawdown_pct
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                payload["run_id"],
                _safe_timestamp(time_value),
                _first_float(point, "strategy_equity", "strategy", "value"),
                _first_float(point, "buy_hold_equity", "buy_hold"),
                _first_float(point, "spy_equity", "spy"),
                drawdown,
            ),
        )


def _db_payload(payload: dict) -> dict:
    database_payload = dict(payload)
    database_payload["request_json"] = Json(payload["request_json"])
    database_payload["metrics_json"] = Json(payload["metrics_json"])
    database_payload["summary_json"] = Json(payload["summary_json"])
    database_payload["diagnostics_json"] = Json(payload["diagnostics_json"])
    return database_payload


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return {}


def _compact_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str, separators=(",", ":"))
    return str(value)


def _chart_length(value: Any):
    return len(value) if isinstance(value, list) else None


def _first_value(mapping: dict, *keys: str):
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _first_float(mapping: dict, *keys: str):
    return safe_float(_first_value(mapping, *keys))


def _safe_timestamp(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    text = safe_str(value)
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        text = f"{text}T00:00:00"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _safe_duration_days(value: Any):
    if isinstance(value, timedelta):
        return value.days

    parsed = safe_int(value)
    if parsed is not None:
        return parsed

    text = safe_str(value)
    if not text:
        return None
    match = re.search(r"-?\d+", text)
    return safe_int(match.group(0)) if match else None


def _time_key(point: dict) -> str:
    return str(point.get("time") or point.get("date") or "")
