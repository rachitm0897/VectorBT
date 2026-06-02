from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.agent.mcp_client.client import call_mcp_tool_sync
from apps.agent.mcp_client.errors import MCPServerUnavailableError, MCPToolError
from apps.agent.mcp_client.schemas import build_strategy_research_arguments


logger = logging.getLogger(__name__)


def run_research_via_mcp(parsed_request: dict[str, Any]) -> dict[str, Any]:
    if not settings.MCP_ENABLED:
        raise MCPServerUnavailableError("The MCP strategy server is disabled.")

    arguments = build_strategy_research_arguments(parsed_request)
    tool_name = settings.MCP_DEFAULT_TOOL
    started = time.perf_counter()
    logger.info(
        "Calling MCP research tool=%s symbol=%s strategy=%s",
        tool_name,
        arguments.get("symbol"),
        arguments.get("strategy"),
    )

    response = call_mcp_tool_sync(tool_name, arguments)
    if response.get("status") != "success":
        raise MCPToolError(str(response.get("message") or "The strategy research tool failed."))

    artifact_result = load_mcp_artifact(str(response.get("artifact_path") or ""))
    logger.info(
        "MCP research completed symbol=%s strategy=%s runtime=%.3fs artifact_loaded=%s",
        arguments.get("symbol"),
        arguments.get("strategy"),
        time.perf_counter() - started,
        bool(artifact_result.get("artifact")),
    )
    return adapt_mcp_research_response(response, artifact_result, arguments)


def load_mcp_artifact(artifact_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {"artifact": None, "warnings": []}
    if not artifact_path:
        result["warnings"].append("Artifact path was not returned; showing summary only.")
        return result

    raw_path = Path(artifact_path)
    if ".." in raw_path.parts:
        result["warnings"].append("Artifact path was rejected; showing summary only.")
        result["error"] = "artifact_path_rejected"
        return result

    allowed_dir = (settings.BASE_DIR.parent / "standalone_mcp_server" / "cache" / "results").resolve()
    candidate = raw_path if raw_path.is_absolute() else settings.BASE_DIR.parent / raw_path
    resolved = candidate.resolve(strict=False)

    try:
        resolved.relative_to(allowed_dir)
    except ValueError:
        result["warnings"].append("Artifact path was rejected; showing summary only.")
        result["error"] = "artifact_path_rejected"
        return result

    if not resolved.exists():
        result["warnings"].append("Artifact could not be loaded; showing summary only.")
        result["error"] = "artifact_missing"
        return result

    try:
        with resolved.open("r", encoding="utf-8") as handle:
            artifact = json.load(handle)
    except (OSError, json.JSONDecodeError):
        result["warnings"].append("Artifact could not be loaded; showing summary only.")
        result["error"] = "artifact_load_failed"
        return result

    if not isinstance(artifact, dict):
        result["warnings"].append("Artifact could not be loaded; showing summary only.")
        result["error"] = "artifact_invalid"
        return result

    result["artifact"] = artifact
    return result


def adapt_mcp_research_response(
    response: dict[str, Any],
    artifact_result: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    artifact = artifact_result.get("artifact") if isinstance(artifact_result.get("artifact"), dict) else {}
    backtest = artifact.get("backtest") if isinstance(artifact.get("backtest"), dict) else {}
    monte_carlo = artifact.get("monte_carlo") if isinstance(artifact.get("monte_carlo"), dict) else {}
    data_quality = _first_dict(response.get("data_quality"), artifact.get("data_quality"))
    metrics = _first_dict(response.get("backtest"), response.get("metrics"), backtest.get("metrics"))
    compact_mc_summary = _first_dict(response.get("monte_carlo"), monte_carlo.get("summary"))
    artifact_path = str(response.get("artifact_path") or "")

    warnings = [
        *(response.get("warnings") if isinstance(response.get("warnings"), list) else []),
        *(artifact_result.get("warnings") if isinstance(artifact_result.get("warnings"), list) else []),
    ]

    return {
        "status": "success",
        "message": "Backtest completed successfully.",
        "request": {
            "symbol": response.get("symbol") or arguments.get("symbol"),
            "strategy": response.get("strategy") or arguments.get("strategy"),
            "parameters": response.get("parameters") or arguments.get("parameters") or {},
        },
        "metrics": metrics,
        "charts": {
            "price": _price_chart(artifact.get("ohlcv")),
            "signals": _signals_chart(artifact.get("ohlcv"), artifact.get("signals")),
            "indicators": _indicators_chart(artifact.get("signals")),
            "equity_curve": _equity_chart(backtest.get("equity_curve")),
            "drawdown_curve": _drawdown_chart(backtest.get("drawdown_curve")),
            "monte_carlo": _monte_carlo_chart(monte_carlo),
        },
        "tables": {
            "trades": backtest.get("trades") if isinstance(backtest.get("trades"), list) else [],
        },
        "summary": _summary(compact_mc_summary),
        "diagnostics": {
            "data_source": "Finnhub via MCP",
            "cache_status": data_quality.get("cache_status", "not reported"),
            "candles_fetched": data_quality.get("candles_fetched", 0),
            "start_date": data_quality.get("start_date"),
            "end_date": data_quality.get("end_date"),
            "mcp_enabled": True,
            "mcp_transport": settings.MCP_TRANSPORT,
            "mcp_tool": settings.MCP_DEFAULT_TOOL,
            "artifact_loaded": bool(artifact),
            "artifact_path": artifact_path,
        },
        "artifact_path": artifact_path,
        "warnings": warnings,
        "errors": [],
    }


def _price_chart(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    chart = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = str(row.get("time") or row.get("date") or "")
        if not date:
            continue
        chart.append(
            {
                "date": date,
                "time": date,
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
            }
        )
    return chart


def _signals_chart(price_rows: Any, signals: Any) -> list[dict[str, Any]]:
    if not isinstance(signals, dict):
        return []
    price_rows = price_rows if isinstance(price_rows, list) else []
    close_by_time = {
        str(row.get("time") or row.get("date")): row.get("close")
        for row in price_rows
        if isinstance(row, dict)
    }
    chart = []
    for source_key, signal_type in (("entries", "entry"), ("exits", "exit")):
        for point in signals.get(source_key) if isinstance(signals.get(source_key), list) else []:
            if not isinstance(point, dict) or not point.get("value"):
                continue
            date = str(point.get("time") or point.get("date") or "")
            if not date:
                continue
            chart.append(
                {
                    "date": date,
                    "time": date,
                    "type": signal_type,
                    "price": close_by_time.get(date),
                }
            )
    return sorted(chart, key=lambda item: item["date"])


def _indicators_chart(signals: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(signals, dict) or not isinstance(signals.get("indicators"), dict):
        return {}
    return {
        name: _time_value_points(points, "value")
        for name, points in signals["indicators"].items()
        if isinstance(points, list)
    }


def _equity_chart(points: Any) -> list[dict[str, Any]]:
    return [
        {"date": point["date"], "time": point["date"], "value": point["value"], "strategy": point["value"]}
        for point in _time_value_points(points, "value")
    ]


def _drawdown_chart(points: Any) -> list[dict[str, Any]]:
    chart = []
    for point in _time_value_points(points, "value"):
        value = point["value"]
        if isinstance(value, (int, float)) and abs(value) <= 1:
            value = value * 100
        chart.append({"date": point["date"], "time": point["date"], "drawdown_pct": value})
    return chart


def _monte_carlo_chart(monte_carlo: dict[str, Any]) -> dict[str, Any]:
    percentile_paths = monte_carlo.get("percentile_paths") if isinstance(monte_carlo, dict) else {}
    sample_paths = monte_carlo.get("sample_paths") if isinstance(monte_carlo, dict) else []
    chart = {
        key: _path_points(percentile_paths.get(key))
        for key in ("p5", "p25", "p50", "p75", "p95")
        if isinstance(percentile_paths, dict)
    }
    chart["sample_paths"] = [
        {"path": index, "values": _path_points(path)}
        for index, path in enumerate(sample_paths if isinstance(sample_paths, list) else [])
        if isinstance(path, list)
    ]
    return chart


def _path_points(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [{"day": index, "value": value} for index, value in enumerate(values)]


def _time_value_points(points: Any, value_key: str) -> list[dict[str, Any]]:
    if not isinstance(points, list):
        return []
    chart = []
    for point in points:
        if not isinstance(point, dict):
            continue
        date = str(point.get("time") or point.get("date") or "")
        if not date:
            continue
        chart.append({"date": date, value_key: point.get("value")})
    return chart


def _summary(monte_carlo_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "monte_carlo_expected_return_pct": monte_carlo_summary.get("expected_return_pct", 0),
        "probability_positive_return_pct": monte_carlo_summary.get("probability_positive_return_pct", 0),
        "p5_return_pct": monte_carlo_summary.get("p5_return_pct", 0),
        "p95_return_pct": monte_carlo_summary.get("p95_return_pct", 0),
    }


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}
