from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import timedelta
from typing import Any, Awaitable, Callable

import requests
from django.conf import settings

from apps.analytics.services import persist_mcp_tool_call
from apps.langsmith_tracing import (
    current_trace_headers,
    get_request_id,
    trace_tool_call,
)

READ_ONLY_DISCOVERY_TOOLS = {
    "list_strategies",
    "get_strategy_schema",
    "list_indicators",
    "get_indicator_info",
}


class MCPClientError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


async def _with_session(
    operation: Callable[[Any], Awaitable[Any]],
    headers: dict[str, str] | None = None,
) -> Any:
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
            headers=headers,
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
            headers=headers,
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


def run_remote_factor_portfolio(
    validated_request: dict[str, Any],
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    arguments = _factor_tool_arguments(validated_request, finnhub_api_key)
    compact = call_mcp_tool("construct_factor_portfolio", arguments)
    _raise_for_tool_error(compact)
    return _factor_backend_response(compact, arguments)


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


def discover_remote_research_name(name: str) -> dict[str, Any]:
    normalized = str(name or "").strip().upper()
    strategies_response = call_mcp_tool("list_strategies", {})
    _raise_for_tool_error(strategies_response)
    strategy_names = [
        str(item.get("name") or "").strip()
        for item in strategies_response.get("strategies", [])
        if isinstance(item, dict) and item.get("name")
    ]
    if normalized.lower() in {strategy.lower() for strategy in strategy_names}:
        return {
            "kind": "strategy",
            "name": normalized.lower(),
            "strategies": strategy_names,
        }

    indicator_response = call_mcp_tool("get_indicator_info", {"indicator": normalized})
    if indicator_response.get("status") != "error":
        return {
            "kind": "indicator",
            "name": normalized,
            "strategies": strategy_names,
            "indicator_info": (
                indicator_response.get("info")
                if isinstance(indicator_response.get("info"), dict)
                else {}
            ),
        }
    return {
        "kind": "unknown",
        "name": normalized,
        "strategies": strategy_names,
    }


def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    _ensure_tool_allowed(tool_name)
    started = time.perf_counter()

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

    with trace_tool_call(
        tool_name,
        arguments,
        metadata={
            "transport": _public_transport(settings.MCP_TRANSPORT),
            "server_url": settings.MCP_SERVER_URL,
            "request_type": _request_type_for_tool(tool_name),
            "selection": "deterministic_after_llm_parse",
        },
    ) as trace_span:
        try:
            compact = _run_async(
                _with_session(operation, headers=current_trace_headers())
            )
        except Exception as exc:
            persist_mcp_tool_call(
                _mcp_tool_event(tool_name, arguments, started, "error", str(exc))
            )
            trace_span.set_error(exc)
            raise

        event_status = "error" if compact.get("status") == "error" else "success"
        persist_mcp_tool_call(
            _mcp_tool_event(
                tool_name,
                arguments,
                started,
                event_status,
                compact.get("message") if event_status == "error" else None,
            )
        )
        trace_span.set_outputs(compact)
        if event_status == "error":
            trace_span.set_error(str(compact.get("message") or "MCP tool returned an error."))
        return compact


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
    monte_carlo = validated_request.get("monte_carlo") or {}
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
        "run_monte_carlo": bool(monte_carlo.get("enabled", False)),
        "monte_carlo_days": int(monte_carlo.get("days", 60)),
        "monte_carlo_simulations": int(monte_carlo.get("simulations", 500)),
        "monte_carlo_block_size": int(monte_carlo.get("block_size", 5)),
        "monte_carlo_seed": monte_carlo.get("seed", 42),
        "monte_carlo_scenarios": list(
            monte_carlo.get("scenarios") or ["neutral", "bullish", "bearish", "crash"]
        ),
        "scenario_overrides": (
            monte_carlo.get("scenario_overrides")
            if isinstance(monte_carlo.get("scenario_overrides"), dict)
            else {}
        ),
    }
    if finnhub_api_key:
        arguments["finnhub_api_key"] = finnhub_api_key
    return arguments


def _factor_tool_arguments(validated_request: dict[str, Any], finnhub_api_key: str | None) -> dict[str, Any]:
    arguments = {
        "symbols": list(validated_request.get("symbols") or []),
        "sector": validated_request.get("sector") or None,
        "selection_mode": validated_request.get("selection_mode", "symbols"),
        "lookback": validated_request.get("lookback", "2y"),
        "resolution": validated_request.get("resolution", "D"),
        "factor_model": validated_request.get("factor_model") if isinstance(validated_request.get("factor_model"), dict) else {},
        "optimization": validated_request.get("optimization") if isinstance(validated_request.get("optimization"), dict) else {},
        "score_tilt": validated_request.get("score_tilt") if isinstance(validated_request.get("score_tilt"), dict) else {},
        "monte_carlo": validated_request.get("monte_carlo") if isinstance(validated_request.get("monte_carlo"), dict) else {},
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
    scenario_analysis = _portfolio_scenario_analysis(compact, artifact)
    if scenario_analysis.get("enabled"):
        charts["scenario_analysis"] = _portfolio_scenario_chart_data(artifact)

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
    if scenario_analysis.get("enabled"):
        portfolio_result["scenario_analysis"] = scenario_analysis

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
            "monte_carlo": {
                "enabled": bool(arguments.get("run_monte_carlo", False)),
                "days": arguments.get("monte_carlo_days"),
                "simulations": arguments.get("monte_carlo_simulations"),
                "block_size": arguments.get("monte_carlo_block_size"),
                "seed": arguments.get("monte_carlo_seed"),
                "scenarios": arguments.get("monte_carlo_scenarios"),
                "scenario_overrides": arguments.get("scenario_overrides") or {},
            },
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


def _factor_backend_response(compact: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    warnings = list(compact.get("warnings") or [])
    artifact = _load_artifact(compact, warnings)
    artifact = artifact if isinstance(artifact, dict) else {}
    factor_scores = artifact.get("factor_scores") if isinstance(artifact.get("factor_scores"), list) else compact.get("factor_scores")
    selected_stocks = artifact.get("selected_stocks") if isinstance(artifact.get("selected_stocks"), list) else compact.get("selected_stocks")
    rejected_stocks = artifact.get("rejected_stocks") if isinstance(artifact.get("rejected_stocks"), list) else compact.get("rejected_stocks")
    optimization_result = (
        artifact.get("optimization_result")
        if isinstance(artifact.get("optimization_result"), dict)
        else compact.get("optimization_result")
    )
    optimization_artifact = (
        _load_artifact(optimization_result, warnings)
        if isinstance(optimization_result, dict) and (
            optimization_result.get("artifact_path") or optimization_result.get("artifact_url") or optimization_result.get("artifact_id")
        )
        else None
    )
    optimization_artifact = optimization_artifact if isinstance(optimization_artifact, dict) else {}
    result = {
        "status": "success",
        "tool": "construct_factor_portfolio",
        "run_id": compact.get("run_id"),
        "request_summary": compact.get("request_summary") if isinstance(compact.get("request_summary"), dict) else {},
        "universe_summary": compact.get("universe_summary") if isinstance(compact.get("universe_summary"), dict) else {},
        "factor_model_configuration": compact.get("factor_model_configuration") if isinstance(compact.get("factor_model_configuration"), dict) else {},
        "factor_scores": factor_scores if isinstance(factor_scores, list) else [],
        "selected_stocks": selected_stocks if isinstance(selected_stocks, list) else [],
        "rejected_stocks": rejected_stocks if isinstance(rejected_stocks, list) else [],
        "optimization_result": optimization_result if isinstance(optimization_result, dict) else {},
        "portfolio_weights": compact.get("portfolio_weights") if isinstance(compact.get("portfolio_weights"), dict) else {},
        "scenario_analysis": compact.get("scenario_analysis") if isinstance(compact.get("scenario_analysis"), dict) else None,
        "scenario_charts": _portfolio_scenario_chart_data(optimization_artifact),
        "data_sources": compact.get("data_sources") if isinstance(compact.get("data_sources"), dict) else {},
        "calculation_timestamp": compact.get("calculation_timestamp"),
        "artifact_id": compact.get("artifact_id"),
        "artifact_url": compact.get("artifact_url"),
        "warnings": warnings,
    }
    return {
        "status": "success",
        "assistant_message": "Factor portfolio construction completed.",
        "parsed_request": {
            "request_type": "factor_portfolio",
            "symbols": arguments.get("symbols") or [],
            "sector": arguments.get("sector"),
            "selection_mode": arguments.get("selection_mode"),
            "lookback": arguments.get("lookback"),
            "resolution": arguments.get("resolution"),
            "factor_model": arguments.get("factor_model") or {},
            "optimization": arguments.get("optimization") or {},
            "score_tilt": arguments.get("score_tilt") or {},
            "monte_carlo": arguments.get("monte_carlo") or {},
        },
        "result_type": "factor_portfolio",
        "factor_portfolio_result": result,
        "diagnostics": {
            "mcp": {
                "enabled": True,
                "transport": _public_transport(settings.MCP_TRANSPORT),
                "server_url": settings.MCP_SERVER_URL,
                "tool": "construct_factor_portfolio",
                "artifact_id": compact.get("artifact_id"),
                "artifact_url": compact.get("artifact_url"),
                "artifact_path": compact.get("artifact_path"),
            }
        },
        "warnings": warnings,
        "errors": [],
    }


def _load_artifact(compact: dict[str, Any], warnings: list[str]) -> dict[str, Any] | None:
    for artifact_url in _artifact_urls(compact):
        try:
            response = requests.get(str(artifact_url), timeout=min(float(settings.MCP_CALL_TIMEOUT_SECONDS), 30.0))
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception:
            continue

    if compact.get("artifact_path"):
        warnings.append("Remote MCP artifact was not accessible from backend.")
    return None


def _artifact_urls(compact: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    public_url = compact.get("artifact_url")
    if public_url:
        urls.append(str(public_url))

    artifact_id = compact.get("artifact_id")
    if artifact_id and settings.MCP_SERVER_URL:
        base_url = settings.MCP_SERVER_URL.rstrip("/")
        for suffix in ("/mcp", "/sse"):
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)]
                break
        urls.append(f"{base_url}/artifacts/{artifact_id}")

    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


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


def _portfolio_scenario_analysis(compact: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    compact_analysis = compact.get("scenario_analysis") if isinstance(compact.get("scenario_analysis"), dict) else {}
    artifact_analysis = artifact.get("scenario_analysis") if isinstance(artifact.get("scenario_analysis"), dict) else {}
    artifact_config = artifact_analysis.get("config") if isinstance(artifact_analysis.get("config"), dict) else {}
    scenarios = compact_analysis.get("scenarios")
    if not isinstance(scenarios, list):
        scenarios = []
        artifact_scenarios = (
            artifact_analysis.get("scenarios") if isinstance(artifact_analysis.get("scenarios"), dict) else {}
        )
        for name, payload in artifact_scenarios.items():
            if not isinstance(payload, dict):
                continue
            scenarios.append(
                {
                    "name": str(name),
                    "label": _scenario_label(str(name)),
                    "assumptions": payload.get("assumptions") if isinstance(payload.get("assumptions"), dict) else {},
                    "summary": payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
                }
            )

    enabled = bool(compact_analysis.get("enabled") or artifact_config.get("enabled") or scenarios)
    if not enabled:
        return {"enabled": False, "config": {}, "scenarios": []}

    config = {
        "enabled": True,
        "days": compact_analysis.get("days", artifact_config.get("days")),
        "simulations": compact_analysis.get("simulations", artifact_config.get("simulations")),
        "block_size": compact_analysis.get("block_size", artifact_config.get("block_size")),
        "seed": compact_analysis.get("seed", artifact_config.get("seed")),
        "portfolio_start_value": compact_analysis.get(
            "portfolio_start_value",
            artifact_config.get("portfolio_start_value"),
        ),
    }
    return {
        "enabled": True,
        "config": config,
        "scenarios": [scenario for scenario in scenarios if isinstance(scenario, dict)],
    }


def _portfolio_scenario_chart_data(artifact: dict[str, Any]) -> dict[str, Any]:
    analysis = artifact.get("scenario_analysis") if isinstance(artifact.get("scenario_analysis"), dict) else {}
    scenarios = analysis.get("scenarios") if isinstance(analysis.get("scenarios"), dict) else {}
    chart_data: dict[str, Any] = {}
    for name, payload in scenarios.items():
        if not isinstance(payload, dict):
            continue
        chart_data[str(name)] = {
            "assumptions": payload.get("assumptions") if isinstance(payload.get("assumptions"), dict) else {},
            "summary": payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
            "percentile_paths": (
                payload.get("percentile_paths") if isinstance(payload.get("percentile_paths"), dict) else {}
            ),
            "sample_paths": payload.get("sample_paths") if isinstance(payload.get("sample_paths"), list) else [],
        }
    return chart_data


def _scenario_label(name: str) -> str:
    return {
        "neutral": "Neutral",
        "bullish": "Bullish",
        "bearish": "Bearish",
        "crash": "Crash",
    }.get(name, name.replace("_", " ").title())


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


def _mcp_tool_event(
    tool_name: str,
    arguments: dict[str, Any],
    started: float,
    status: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    symbols = arguments.get("symbols")
    return {
        "request_id": get_request_id(),
        "tool_name": tool_name,
        "transport": _public_transport(settings.MCP_TRANSPORT),
        "server_url": settings.MCP_SERVER_URL,
        "status": status,
        "runtime_ms": int((time.perf_counter() - started) * 1000),
        "error_message": error_message,
        "request_type": _request_type_for_tool(tool_name),
        "symbol": arguments.get("symbol"),
        "strategy": arguments.get("strategy"),
        "sector": arguments.get("sector"),
        "symbols_count": len(symbols) if isinstance(symbols, list) else None,
    }


def _request_type_for_tool(tool_name: str) -> str | None:
    if tool_name == "construct_factor_portfolio":
        return "factor_portfolio"
    if tool_name == "run_markowitz_optimization":
        return "portfolio_optimization"
    if tool_name in {"run_strategy_research", "run_strategy_backtest"}:
        return "strategy_backtest"
    return None


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
    allowed.update(READ_ONLY_DISCOVERY_TOOLS)
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
