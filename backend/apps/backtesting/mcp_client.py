from __future__ import annotations

import asyncio
import json
import os
from datetime import timedelta
from typing import Any, Awaitable, Callable

import requests
from django.conf import settings


class MCPClientError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


async def _with_session(operation: Callable[[Any], Awaitable[Any]]) -> Any:
    from mcp.client.session import ClientSession

    timeout_seconds = float(settings.MCP_CALL_TIMEOUT_SECONDS)
    read_timeout = timedelta(seconds=timeout_seconds)
    transport = _sdk_transport(settings.MCP_TRANSPORT)

    if transport == "streamable-http":
        from mcp.client.streamable_http import streamablehttp_client

        if not settings.MCP_SERVER_URL:
            raise MCPClientError("missing_mcp_server_url", "MCP_SERVER_URL is required for remote MCP transport.")
        async with streamablehttp_client(
            settings.MCP_SERVER_URL,
            timeout=timeout_seconds,
            sse_read_timeout=timeout_seconds,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=read_timeout) as session:
                await session.initialize()
                return await operation(session)

    if transport == "sse":
        from mcp.client.sse import sse_client

        if not settings.MCP_SERVER_URL:
            raise MCPClientError("missing_mcp_server_url", "MCP_SERVER_URL is required for remote MCP transport.")
        async with sse_client(
            settings.MCP_SERVER_URL,
            timeout=timeout_seconds,
            sse_read_timeout=timeout_seconds,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=read_timeout) as session:
                await session.initialize()
                return await operation(session)

    if transport == "stdio":
        from mcp.client.stdio import StdioServerParameters, stdio_client

        if not settings.MCP_SERVER_COMMAND:
            raise MCPClientError("missing_mcp_server_command", "MCP_SERVER_COMMAND is required for stdio MCP transport.")
        env = os.environ.copy()
        env["MCP_TRANSPORT"] = "stdio"
        params = StdioServerParameters(
            command=settings.MCP_SERVER_COMMAND,
            args=list(settings.MCP_SERVER_ARGS),
            env=env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=read_timeout) as session:
                await session.initialize()
                return await operation(session)

    raise MCPClientError("unsupported_mcp_transport", f"Unsupported MCP transport: {settings.MCP_TRANSPORT}.")


def get_mcp_status() -> dict[str, Any]:
    status = {
        "enabled": bool(settings.MCP_ENABLED),
        "transport": _public_transport(settings.MCP_TRANSPORT),
        "server_url": settings.MCP_SERVER_URL,
        "connected": False,
        "tools": [],
        "approved_tools": sorted(_allowed_mcp_tools()),
        "error": None,
    }
    if not settings.MCP_ENABLED:
        return status

    try:
        status["tools"] = list_mcp_tools()
        status["connected"] = True
    except MCPClientError as exc:
        status["error"] = str(exc)
    except Exception:
        status["error"] = "Could not connect to MCP server."
    return status


def list_mcp_tools() -> list[str]:
    async def operation(session: Any) -> list[str]:
        result = await session.list_tools()
        return [tool.name for tool in result.tools]

    return _run_async(_with_session(operation))


def run_remote_backtest(validated_request: dict[str, Any], finnhub_api_key: str | None = None) -> dict[str, Any]:
    arguments = _tool_arguments(validated_request, finnhub_api_key)
    compact = call_mcp_tool(settings.MCP_DEFAULT_TOOL, arguments)
    _raise_for_tool_error(compact)
    return _backend_response(compact, arguments)


def run_remote_portfolio_optimization(
    validated_request: dict[str, Any],
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    arguments = _portfolio_tool_arguments(validated_request, finnhub_api_key)
    compact = call_mcp_tool("run_markowitz_optimization", arguments)
    _raise_for_tool_error(compact)
    return _portfolio_backend_response(compact, arguments)


def fetch_remote_sectors() -> dict[str, Any]:
    compact = call_mcp_tool("list_sectors", {})
    _raise_for_tool_error(compact)
    return {
        "status": "success",
        "sectors": compact.get("sectors") if isinstance(compact.get("sectors"), list) else [],
    }


def fetch_remote_stocks_by_sector(sector: str | None = None) -> dict[str, Any]:
    if sector:
        compact = call_mcp_tool("list_stock_universe", {"sector": sector, "limit": 500})
    else:
        compact = call_mcp_tool("list_stock_universe", {"sector": None, "limit": 500})
    _raise_for_tool_error(compact)
    return {
        "status": "success",
        "sector": compact.get("sector") or sector or "",
        "count": int(compact.get("count") or len(compact.get("stocks") or [])),
        "stocks": compact.get("stocks") if isinstance(compact.get("stocks"), list) else [],
    }


def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    _ensure_tool_allowed(tool_name)

    async def operation(session: Any) -> dict[str, Any]:
        result = await session.call_tool(
            tool_name,
            arguments=arguments,
            read_timeout_seconds=timedelta(seconds=float(settings.MCP_CALL_TIMEOUT_SECONDS)),
        )
        if getattr(result, "isError", False):
            data = _decode_tool_result(result)
            message = str(data.get("message") or "MCP tool call failed.")
            errors = data.get("errors") if isinstance(data.get("errors"), list) else ["mcp_tool_error"]
            raise MCPClientError(str(errors[0]), message)
        return _decode_tool_result(result)

    return _run_async(_with_session(operation))


def _raise_for_tool_error(compact: dict[str, Any]) -> None:
    if compact.get("status") != "error":
        return
    errors = compact.get("errors") if isinstance(compact.get("errors"), list) else []
    code = str(errors[0]) if errors else "mcp_tool_error"
    message = str(compact.get("message") or "MCP tool returned an error.")
    raise MCPClientError(code, message)


def _tool_arguments(validated_request: dict[str, Any], finnhub_api_key: str | None) -> dict[str, Any]:
    monte_carlo = validated_request.get("monte_carlo") or {}
    arguments = {
        "symbol": validated_request["symbol"],
        "strategy": validated_request["strategy"],
        "parameters": validated_request.get("parameters") or {},
        "lookback": validated_request.get("lookback", "2y"),
        "resolution": validated_request.get("resolution", "D"),
        "initial_cash": float(validated_request.get("initial_cash", 10000.0)),
        "fees": float(validated_request.get("fees", 0.001)),
        "run_monte_carlo": bool(monte_carlo.get("enabled", True)),
        "monte_carlo_days": int(monte_carlo.get("days", 60)),
        "monte_carlo_simulations": int(monte_carlo.get("simulations", 500)),
    }
    if finnhub_api_key:
        arguments["finnhub_api_key"] = finnhub_api_key
    return arguments


def _portfolio_tool_arguments(validated_request: dict[str, Any], finnhub_api_key: str | None) -> dict[str, Any]:
    arguments = {
        "symbols": list(validated_request.get("symbols") or []),
        "sector": validated_request.get("sector") or None,
        "lookback": validated_request.get("lookback", "2y"),
        "resolution": validated_request.get("resolution", "D"),
        "objective": validated_request.get("objective", "max_sharpe"),
        "risk_free_rate": float(validated_request.get("risk_free_rate", 0.0)),
        "allow_short": bool(validated_request.get("allow_short", False)),
        "max_weight": float(validated_request.get("max_weight", 0.6)),
        "num_frontier_portfolios": int(validated_request.get("num_frontier_portfolios", 3000)),
    }
    if finnhub_api_key:
        arguments["finnhub_api_key"] = finnhub_api_key
    return arguments


def _backend_response(compact: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    warnings = list(compact.get("warnings") or [])
    artifact = _load_artifact(compact, warnings)
    artifact = artifact if isinstance(artifact, dict) else {}
    artifact_backtest = artifact.get("backtest") if isinstance(artifact.get("backtest"), dict) else {}

    metrics = _normalize_metrics(compact.get("backtest") or compact.get("metrics") or artifact_backtest.get("metrics") or {})
    summary = _normalize_summary(compact.get("monte_carlo") or (artifact.get("monte_carlo") or {}).get("summary") or {})
    symbol = str(compact.get("symbol") or artifact.get("symbol") or arguments.get("symbol"))
    strategy = str(compact.get("strategy") or artifact.get("strategy") or arguments.get("strategy"))
    parameters = compact.get("parameters") or artifact.get("parameters") or arguments.get("parameters") or {}

    return {
        "status": "success",
        "message": "Backtest completed successfully.",
        "request": {
            "symbol": symbol,
            "strategy": strategy,
            "parameters": parameters,
        },
        "metrics": metrics,
        "charts": {
            "price": _price_chart(artifact.get("ohlcv")),
            "signals": _signals_chart(artifact),
            "indicators": _indicator_charts(artifact),
            "equity_curve": _series_chart(artifact_backtest.get("equity_curve"), "value"),
            "drawdown_curve": _series_chart(artifact_backtest.get("drawdown_curve"), "drawdown_pct", multiplier=100.0),
            "monte_carlo": _monte_carlo_chart(artifact.get("monte_carlo")),
        },
        "tables": {
            "trades": artifact_backtest.get("trades") if isinstance(artifact_backtest.get("trades"), list) else [],
        },
        "summary": summary,
        "diagnostics": {
            "mcp": {
                "enabled": True,
                "transport": _public_transport(settings.MCP_TRANSPORT),
                "server_url": settings.MCP_SERVER_URL,
                "tool": settings.MCP_DEFAULT_TOOL,
                "run_id": compact.get("run_id"),
                "artifact_id": compact.get("artifact_id"),
                "artifact_url": compact.get("artifact_url"),
                "artifact_path": compact.get("artifact_path"),
                "data_quality": compact.get("data_quality"),
            }
        },
        "warnings": warnings,
        "errors": [],
    }


def _portfolio_backend_response(compact: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    warnings = list(compact.get("warnings") or [])
    artifact = _load_artifact(compact, warnings)
    artifact = artifact if isinstance(artifact, dict) else {}
    charts = {
        "random_portfolios": _artifact_list(artifact, compact, "random_portfolios"),
        "efficient_frontier": _artifact_list(artifact, compact, "efficient_frontier"),
        "min_volatility_portfolio": _artifact_dict(artifact, compact, "min_volatility_portfolio"),
        "max_sharpe_portfolio": _artifact_dict(artifact, compact, "max_sharpe_portfolio"),
        "individual_assets": _artifact_list(artifact, compact, "individual_assets"),
        "correlation_matrix": _artifact_list(artifact, compact, "correlation_matrix"),
    }

    portfolio_result = {
        "status": "success",
        "objective": compact.get("objective") or arguments.get("objective"),
        "symbols": compact.get("symbols") or arguments.get("symbols") or [],
        "selection_mode": compact.get("selection_mode") or ("sector" if compact.get("sector") else "symbols"),
        "sector": compact.get("sector"),
        "symbols_used": compact.get("symbols_used") or compact.get("symbols") or arguments.get("symbols") or [],
        "rejected_symbols": compact.get("rejected_symbols") or [],
        "weights": compact.get("weights") if isinstance(compact.get("weights"), dict) else {},
        "metrics": compact.get("metrics") if isinstance(compact.get("metrics"), dict) else {},
        "data_quality": compact.get("data_quality") if isinstance(compact.get("data_quality"), dict) else {},
        "artifact_id": compact.get("artifact_id"),
        "artifact_url": compact.get("artifact_url"),
        "charts": charts,
        "warnings": warnings,
    }

    return {
        "status": "success",
        "assistant_message": "Portfolio optimization completed.",
        "parsed_request": {
            "request_type": "portfolio_optimization",
            "symbols": arguments.get("symbols") or [],
            "sector": arguments.get("sector"),
            "lookback": arguments.get("lookback"),
            "resolution": arguments.get("resolution"),
            "objective": arguments.get("objective"),
            "risk_free_rate": arguments.get("risk_free_rate"),
            "allow_short": arguments.get("allow_short"),
            "max_weight": arguments.get("max_weight"),
            "num_frontier_portfolios": arguments.get("num_frontier_portfolios"),
        },
        "result_type": "portfolio_optimization",
        "portfolio_result": portfolio_result,
        "diagnostics": {
            "mcp": {
                "enabled": True,
                "transport": _public_transport(settings.MCP_TRANSPORT),
                "server_url": settings.MCP_SERVER_URL,
                "tool": "run_markowitz_optimization",
                "artifact_id": compact.get("artifact_id"),
                "artifact_url": compact.get("artifact_url"),
                "artifact_path": compact.get("artifact_path"),
                "data_quality": compact.get("data_quality"),
            }
        },
        "warnings": warnings,
        "errors": [],
    }


def _load_artifact(compact: dict[str, Any], warnings: list[str]) -> dict[str, Any] | None:
    artifact_url = compact.get("artifact_url")
    if artifact_url:
        try:
            response = requests.get(str(artifact_url), timeout=min(float(settings.MCP_CALL_TIMEOUT_SECONDS), 30.0))
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception:
            warnings.append("Remote MCP artifact could not be loaded; showing compact summary.")
            return None

    if compact.get("artifact_path"):
        warnings.append("Remote MCP artifact was not accessible from backend.")
    return None


def _artifact_list(
    artifact: dict[str, Any],
    compact: dict[str, Any],
    key: str,
) -> list[Any]:
    value = artifact.get(key)
    if isinstance(value, list):
        return value
    value = compact.get(key)
    return value if isinstance(value, list) else []


def _artifact_dict(
    artifact: dict[str, Any],
    compact: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    value = artifact.get(key)
    if isinstance(value, dict):
        return value
    value = compact.get(key)
    return value if isinstance(value, dict) else {}


def _decode_tool_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    text_parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            text_parts.append(text)
    text = "\n".join(text_parts).strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "success", "content": text}
    return data if isinstance(data, dict) else {"status": "success", "content": data}


def _normalize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(metrics) if isinstance(metrics, dict) else {}
    max_drawdown = _to_float(cleaned.get("max_drawdown_pct"))
    if max_drawdown is not None:
        cleaned["max_drawdown_pct"] = abs(max_drawdown)
    return cleaned


def _normalize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    cleaned = dict(summary)
    if "expected_return_pct" in cleaned and "monte_carlo_expected_return_pct" not in cleaned:
        cleaned["monte_carlo_expected_return_pct"] = cleaned["expected_return_pct"]
    return cleaned


def _price_chart(ohlcv: Any) -> list[dict[str, Any]]:
    if not isinstance(ohlcv, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in ohlcv:
        if not isinstance(item, dict):
            continue
        date = item.get("date") or item.get("time")
        if not date:
            continue
        rows.append(
            {
                "date": str(date),
                "time": str(date),
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": item.get("close"),
                "volume": item.get("volume"),
            }
        )
    return rows


def _signals_chart(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    signals = artifact.get("signals") if isinstance(artifact.get("signals"), dict) else {}
    close_by_time = {
        str(item.get("date") or item.get("time")): item.get("close")
        for item in artifact.get("ohlcv", [])
        if isinstance(item, dict) and (item.get("date") or item.get("time"))
    }
    rows: list[dict[str, Any]] = []
    for key, signal_type in (("entries", "entry"), ("exits", "exit")):
        for point in signals.get(key, []) if isinstance(signals.get(key), list) else []:
            if not isinstance(point, dict) or not _truthy_number(point.get("value")):
                continue
            date = str(point.get("date") or point.get("time") or "")
            if not date:
                continue
            rows.append({"date": date, "time": date, "type": signal_type, "price": close_by_time.get(date)})
    return sorted(rows, key=lambda item: item["date"])


def _indicator_charts(artifact: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    signals = artifact.get("signals") if isinstance(artifact.get("signals"), dict) else {}
    indicators = signals.get("indicators") if isinstance(signals.get("indicators"), dict) else {}
    return {name: _series_chart(points, "value") for name, points in indicators.items()}


def _series_chart(points: Any, value_key: str, multiplier: float = 1.0) -> list[dict[str, Any]]:
    if not isinstance(points, list):
        return []
    rows: list[dict[str, Any]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        date = point.get("date") or point.get("time")
        value = _to_float(point.get("value"))
        if not date or value is None:
            continue
        rows.append({"date": str(date), "time": str(date), value_key: value * multiplier})
    return rows


def _monte_carlo_chart(simulation: Any) -> dict[str, Any]:
    if not isinstance(simulation, dict):
        return {"p5": [], "p25": [], "p50": [], "p75": [], "p95": [], "sample_paths": []}
    percentile_paths = simulation.get("percentile_paths") if isinstance(simulation.get("percentile_paths"), dict) else {}
    chart = {
        key: [{"day": index, "value": value} for index, value in enumerate(percentile_paths.get(key, []) or [])]
        for key in ("p5", "p25", "p50", "p75", "p95")
    }
    chart["sample_paths"] = [
        {"path": index, "values": [{"day": day, "value": value} for day, value in enumerate(path)]}
        for index, path in enumerate(simulation.get("sample_paths", []) or [])
        if isinstance(path, list)
    ]
    return chart


def _sdk_transport(value: str) -> str:
    normalized = (value or "stdio").strip().lower().replace("_", "-")
    if normalized == "streamable-http":
        return normalized
    return normalized


def _public_transport(value: str) -> str:
    return _sdk_transport(value).replace("-", "_")


def _allowed_mcp_tools() -> set[str]:
    allowed = set(getattr(settings, "MCP_ALLOWED_TOOLS", set()) or set())
    if settings.MCP_DEFAULT_TOOL:
        allowed.add(settings.MCP_DEFAULT_TOOL)
    return allowed


def _ensure_tool_allowed(tool_name: str) -> None:
    if tool_name not in _allowed_mcp_tools():
        raise MCPClientError("mcp_tool_not_allowed", f"MCP tool is not approved: {tool_name}.")


def _run_async(awaitable: Awaitable[Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise MCPClientError("mcp_async_context", "MCP client cannot run inside an active event loop.")


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy_number(value: Any) -> bool:
    parsed = _to_float(value)
    return bool(parsed and parsed != 0)
