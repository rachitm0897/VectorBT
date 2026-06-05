from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError
from starlette.responses import FileResponse, JSONResponse

from tools.backtesting import run_vectorbt_backtest
from tools.cache import cache_dir
from tools.formatting import (
    compact_backtest_response,
    compact_monte_carlo_response,
    compact_research_response,
    save_artifact_json,
    series_to_points,
)
from tools.market_data import fetch_finnhub_candles_with_metadata
from tools.monte_carlo import run_bootstrap_monte_carlo
from tools.portfolio_optimization import run_markowitz_optimization_core
from tools.schemas import (
    IndicatorBatchRequest,
    IndicatorRequest,
    MarketDataRequest,
    MonteCarloRequest,
    StrategyBacktestRequest,
    StrategyResearchRequest,
    parse_request,
)
from tools.strategies import generate_strategy_signals, list_strategy_definitions, strategy_schema
from tools.talib_adapter import (
    compute_talib_indicator,
    get_talib_indicator_info,
    list_talib_indicators,
)
from tools.tracing import configure_langsmith_middleware, get_request_id, traced_tool
from tools.universe import (
    list_all_stocks as universe_list_all_stocks,
    list_sectors as universe_list_sectors,
    list_stocks_by_sector as universe_list_stocks_by_sector,
    resolve_symbols_for_sector as universe_resolve_symbols_for_sector,
)


SERVER_ROOT = Path(__file__).resolve().parent
load_dotenv(SERVER_ROOT / ".env")
load_dotenv()
logger = logging.getLogger("insta_mcpserver")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _normalize_path(value: str, default: str) -> str:
    path = (value or default).strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or default


MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_SERVER_PORT = _env_int("MCP_SERVER_PORT", _env_int("PORT", 8001))
MCP_BASE_PATH = _normalize_path(os.getenv("MCP_BASE_PATH", "/mcp"), "/mcp")
MCP_SSE_PATH = _normalize_path(os.getenv("MCP_SSE_PATH", "/sse"), "/sse")
MCP_PROXY_PREFIX = _normalize_path(
    os.getenv("MCP_PROXY_PREFIX", "/insta_backtest_MCP_server"),
    "/insta_backtest_MCP_server",
)

mcp = FastMCP(
    "VectorBT Standalone Strategy Server",
    host=MCP_SERVER_HOST,
    port=MCP_SERVER_PORT,
    streamable_http_path=MCP_BASE_PATH,
    sse_path=MCP_SSE_PATH,
)


def _error_response(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "errors": errors or ["unknown_error"],
    }


def _unexpected_error_response(context: str, exc: Exception) -> dict[str, Any]:
    logger.exception("%s failed [request_id=%s]: %s", context, get_request_id(), exc)
    message = str(exc).strip() or f"Unexpected error while running {context}."
    return _error_response(message, ["unexpected_error"])


def _validation_error_response(exc: ValidationError) -> dict[str, Any]:
    codes: list[str] = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err.get("loc", []))
        code = err.get("type", "validation_error")
        codes.append(f"{location}:{code}" if location else code)
    return _error_response("Invalid request parameters.", codes or ["validation_error"])


def _value_error_response(exc: ValueError, fallback_code: str) -> dict[str, Any]:
    message = str(exc)
    if message == "Finnhub API key is required.":
        return _error_response(message, ["missing_finnhub_api_key"])
    return _error_response(message, [fallback_code])


def _data_quality(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "candles_fetched": metadata.get("candles_fetched", 0),
        "start_date": metadata.get("start_date"),
        "end_date": metadata.get("end_date"),
        "cache_status": metadata.get("cache_status", "MISS"),
    }


def _signals_artifact(signals: dict[str, Any]) -> dict[str, Any]:
    entries = signals["entries"]
    exits = signals["exits"]
    indicators = signals.get("indicators", {})
    return {
        "entries": series_to_points(entries.astype(int)),
        "exits": series_to_points(exits.astype(int)),
        "indicators": {name: series_to_points(values) for name, values in indicators.items()},
    }


def _serialize_indicator_outputs(
    outputs: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    return {name: series_to_points(values) for name, values in outputs.items()}


def _run_backtest_components(
    request: StrategyBacktestRequest | StrategyResearchRequest,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    df, metadata = fetch_finnhub_candles_with_metadata(
        request.symbol,
        lookback=request.lookback,
        resolution=request.resolution,
        api_key=request.finnhub_api_key,
    )
    signals = generate_strategy_signals(df, request.strategy, request.parameters)
    backtest = run_vectorbt_backtest(
        df,
        signals["entries"],
        signals["exits"],
        initial_cash=request.initial_cash,
        fees=request.fees,
    )
    effective_parameters = signals.get("parameters", request.parameters)
    artifact = {
        "symbol": metadata["symbol"],
        "strategy": request.strategy,
        "parameters": effective_parameters,
        "lookback": request.lookback,
        "resolution": request.resolution,
        "data_quality": _data_quality(metadata),
        "ohlcv": df,
        "signals": _signals_artifact(signals),
        "backtest": backtest,
    }
    return backtest, artifact, metadata, signals


@mcp.tool()
@traced_tool()
def list_strategies() -> dict[str, Any]:
    """List supported prototype trading strategies."""
    return {"status": "success", "strategies": list_strategy_definitions()}


@mcp.tool()
@traced_tool()
def get_strategy_schema(strategy: str) -> dict[str, Any]:
    """Return the parameter schema for a supported strategy."""
    try:
        return {
            "status": "success",
            "strategy": strategy,
            "parameters": strategy_schema(strategy),
        }
    except ValueError as exc:
        return _error_response(str(exc), ["unsupported_strategy"])


@mcp.tool()
@traced_tool()
def list_indicators() -> dict[str, Any]:
    """List TA-Lib indicators available through the finance indicator workflow."""
    return {"status": "success", "indicators": list_talib_indicators()}


@mcp.tool()
@traced_tool()
def get_indicator_info(indicator: str) -> dict[str, Any]:
    """Return TA-Lib metadata for one indicator."""
    try:
        normalized = str(indicator or "").strip().upper()
        return {
            "status": "success",
            "indicator": normalized,
            "info": get_talib_indicator_info(normalized),
        }
    except ValueError as exc:
        return _error_response(str(exc), ["unsupported_indicator"])


@mcp.tool()
@traced_tool()
def compute_indicator(
    symbol: str,
    indicator: str,
    parameters: dict[str, Any] | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch one symbol and compute one TA-Lib indicator."""
    try:
        request = parse_request(
            IndicatorRequest,
            {
                "symbol": symbol,
                "indicator": indicator,
                "parameters": parameters or {},
                "lookback": lookback,
                "resolution": resolution,
                "finnhub_api_key": finnhub_api_key,
            },
        )
        df, metadata = fetch_finnhub_candles_with_metadata(
            request.symbol,
            lookback=request.lookback,
            resolution=request.resolution,
            api_key=request.finnhub_api_key,
        )
        normalized = request.indicator.strip().upper()
        outputs = compute_talib_indicator(df, normalized, request.parameters)
        return {
            "status": "success",
            "symbol": metadata["symbol"],
            "indicator": normalized,
            "parameters": request.parameters,
            "lookback": request.lookback,
            "resolution": request.resolution,
            "data_quality": _data_quality(metadata),
            "outputs": _serialize_indicator_outputs(outputs),
        }
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "indicator_error")
    except Exception as exc:
        return _unexpected_error_response("indicator computation", exc)


@mcp.tool()
@traced_tool()
def compute_indicators_batch(
    symbol: str,
    indicators: list[dict[str, Any]],
    lookback: str = "2y",
    resolution: str = "D",
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch one symbol once and compute multiple TA-Lib indicators."""
    try:
        request = parse_request(
            IndicatorBatchRequest,
            {
                "symbol": symbol,
                "indicators": indicators,
                "lookback": lookback,
                "resolution": resolution,
                "finnhub_api_key": finnhub_api_key,
            },
        )
        df, metadata = fetch_finnhub_candles_with_metadata(
            request.symbol,
            lookback=request.lookback,
            resolution=request.resolution,
            api_key=request.finnhub_api_key,
        )

        results: list[dict[str, Any]] = []
        indicator_errors: list[dict[str, Any]] = []
        for spec in request.indicators:
            normalized = spec.name.strip().upper()
            try:
                outputs = compute_talib_indicator(df, normalized, spec.parameters)
                result = {
                    "indicator": normalized,
                    "parameters": spec.parameters,
                    "outputs": _serialize_indicator_outputs(outputs),
                }
                if spec.alias:
                    result["alias"] = spec.alias
                results.append(result)
            except ValueError as exc:
                error = {
                    "indicator": normalized,
                    "message": str(exc),
                }
                if spec.alias:
                    error["alias"] = spec.alias
                indicator_errors.append(error)

        status = "success"
        if indicator_errors and results:
            status = "partial_success"
        elif indicator_errors:
            status = "error"

        response = {
            "status": status,
            "symbol": metadata["symbol"],
            "lookback": request.lookback,
            "resolution": request.resolution,
            "data_quality": _data_quality(metadata),
            "indicators": results,
            "indicator_errors": indicator_errors,
        }
        if not results:
            response["message"] = "No indicators were computed successfully."
            response["errors"] = ["indicator_computation_failed"]
        return response
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "indicator_batch_error")
    except Exception as exc:
        return _unexpected_error_response("batch indicator computation", exc)


@mcp.tool()
@traced_tool()
def list_stock_universe(sector: str | None = None, limit: int = 500) -> dict[str, Any]:
    """List compact US stock universe records, optionally filtered by sector."""
    try:
        parsed_limit = max(1, min(int(limit or 500), 500))
        requested_sector = str(sector or "").strip() or None
        stocks = (
            universe_list_stocks_by_sector(requested_sector)
            if requested_sector
            else universe_list_all_stocks()
        )[:parsed_limit]
        return {
            "status": "success",
            "count": len(stocks),
            "sector": requested_sector,
            "stocks": stocks,
        }
    except FileNotFoundError as exc:
        return _error_response(str(exc), ["universe_file_missing"])
    except Exception as exc:
        return _unexpected_error_response("stock universe loading", exc)


@mcp.tool()
@traced_tool()
def list_sectors() -> dict[str, Any]:
    """List sectors found in the US stock universe."""
    try:
        return {"status": "success", "sectors": universe_list_sectors()}
    except FileNotFoundError as exc:
        return _error_response(str(exc), ["universe_file_missing"])
    except Exception as exc:
        return _unexpected_error_response("sector loading", exc)


@mcp.tool()
@traced_tool()
def list_stocks_by_sector(sector: str) -> dict[str, Any]:
    """List compact US stock records for one sector."""
    try:
        stocks = universe_list_stocks_by_sector(sector)
        return {"status": "success", "sector": sector, "count": len(stocks), "stocks": stocks}
    except FileNotFoundError as exc:
        return _error_response(str(exc), ["universe_file_missing"])
    except Exception as exc:
        return _unexpected_error_response("stocks by sector loading", exc)


@mcp.tool()
@traced_tool()
def resolve_symbols_for_sector(sector: str) -> dict[str, Any]:
    """Resolve all ticker symbols for a sector in the US stock universe."""
    try:
        symbols = universe_resolve_symbols_for_sector(sector)
        return {
            "status": "success",
            "sector": sector,
            "symbols": symbols,
            "count": len(symbols),
        }
    except FileNotFoundError as exc:
        return _error_response(str(exc), ["universe_file_missing"])
    except Exception as exc:
        return _unexpected_error_response("sector symbol resolution", exc)


@mcp.tool()
@traced_tool()
def fetch_market_data_summary(
    symbol: str,
    lookback: str = "2y",
    resolution: str = "D",
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch Finnhub OHLCV data and return a compact data quality summary."""
    try:
        request = parse_request(
            MarketDataRequest,
            {
                "symbol": symbol,
                "lookback": lookback,
                "resolution": resolution,
                "finnhub_api_key": finnhub_api_key,
            },
        )
        _, metadata = fetch_finnhub_candles_with_metadata(
            request.symbol,
            lookback=request.lookback,
            resolution=request.resolution,
            api_key=request.finnhub_api_key,
        )
        return {
            "status": "success",
            "symbol": metadata["symbol"],
            "resolution": request.resolution,
            "lookback": request.lookback,
            "candles_fetched": metadata["candles_fetched"],
            "start_date": metadata["start_date"],
            "end_date": metadata["end_date"],
            "cache_status": metadata["cache_status"],
        }
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "market_data_error")
    except Exception as exc:
        return _unexpected_error_response("market data fetch", exc)


@mcp.tool()
@traced_tool()
def run_strategy_backtest(
    symbol: str,
    strategy: str,
    parameters: dict[str, Any] | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    initial_cash: float | None = None,
    fees: float | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Run one strategy backtest and return compact metrics plus an artifact path."""
    try:
        payload = {
            "symbol": symbol,
            "strategy": strategy,
            "parameters": parameters or {},
            "lookback": lookback,
            "resolution": resolution,
            "finnhub_api_key": finnhub_api_key,
        }
        if initial_cash is not None:
            payload["initial_cash"] = initial_cash
        if fees is not None:
            payload["fees"] = fees
        request = parse_request(StrategyBacktestRequest, payload)
        backtest, artifact, metadata, _ = _run_backtest_components(request)
        artifact_path = save_artifact_json(backtest["run_id"], artifact)
        return compact_backtest_response(
            run_id=backtest["run_id"],
            symbol=metadata["symbol"],
            strategy=request.strategy,
            parameters=artifact["parameters"],
            lookback=request.lookback,
            metrics=backtest["metrics"],
            data_quality=_data_quality(metadata),
            artifact_path=artifact_path,
            warnings=backtest.get("warnings", []),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "backtest_error")
    except RuntimeError as exc:
        return _error_response(str(exc), ["runtime_error"])
    except Exception as exc:
        return _unexpected_error_response("strategy backtest", exc)


@mcp.tool()
@traced_tool()
def run_monte_carlo_simulation(
    symbol: str,
    lookback: str = "2y",
    resolution: str = "D",
    start_value: float = 10000,
    days: int = 60,
    simulations: int = 500,
    method: str = "bootstrap",
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Run a bootstrap Monte Carlo simulation and return a compact summary."""
    try:
        request = parse_request(
            MonteCarloRequest,
            {
                "symbol": symbol,
                "lookback": lookback,
                "resolution": resolution,
                "start_value": start_value,
                "days": days,
                "simulations": simulations,
                "method": method,
                "finnhub_api_key": finnhub_api_key,
            },
        )
        df, metadata = fetch_finnhub_candles_with_metadata(
            request.symbol,
            lookback=request.lookback,
            resolution=request.resolution,
            api_key=request.finnhub_api_key,
        )
        simulation = run_bootstrap_monte_carlo(
            df["close"],
            start_value=request.start_value,
            days=request.days,
            simulations=request.simulations,
        )
        run_id = simulation["run_id"]
        artifact = {
            "symbol": metadata["symbol"],
            "method": request.method,
            "lookback": request.lookback,
            "resolution": request.resolution,
            "data_quality": _data_quality(metadata),
            "ohlcv": df,
            "monte_carlo": simulation,
        }
        artifact_path = save_artifact_json(run_id, artifact)
        return compact_monte_carlo_response(
            symbol=metadata["symbol"],
            method=request.method,
            days=request.days,
            simulations=request.simulations,
            summary=simulation["summary"],
            artifact_path=artifact_path,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "monte_carlo_error")
    except Exception as exc:
        return _unexpected_error_response("Monte Carlo simulation", exc)


@mcp.tool()
@traced_tool()
def run_strategy_research(
    symbol: str,
    strategy: str,
    parameters: dict[str, Any] | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    initial_cash: float | None = None,
    fees: float | None = None,
    run_monte_carlo: bool = True,
    monte_carlo_days: int = 60,
    monte_carlo_simulations: int = 500,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Run the full prototype research workflow for one symbol and strategy."""
    try:
        payload = {
            "symbol": symbol,
            "strategy": strategy,
            "parameters": parameters or {},
            "lookback": lookback,
            "resolution": resolution,
            "run_monte_carlo": run_monte_carlo,
            "monte_carlo_days": monte_carlo_days,
            "monte_carlo_simulations": monte_carlo_simulations,
            "finnhub_api_key": finnhub_api_key,
        }
        if initial_cash is not None:
            payload["initial_cash"] = initial_cash
        if fees is not None:
            payload["fees"] = fees
        request = parse_request(StrategyResearchRequest, payload)
        backtest, artifact, metadata, _ = _run_backtest_components(request)

        monte_carlo_summary = None
        if request.run_monte_carlo:
            simulation = run_bootstrap_monte_carlo(
                artifact["ohlcv"]["close"],
                start_value=backtest["metrics"]["final_value"],
                days=request.monte_carlo_days,
                simulations=request.monte_carlo_simulations,
            )
            artifact["monte_carlo"] = simulation
            monte_carlo_summary = simulation["summary"]

        run_id = f"research_{backtest['run_id'].split('_', 1)[-1]}"
        artifact["run_id"] = run_id
        artifact_path = save_artifact_json(run_id, artifact)
        return compact_research_response(
            run_id=run_id,
            symbol=metadata["symbol"],
            strategy=request.strategy,
            parameters=artifact["parameters"],
            backtest=backtest["metrics"],
            monte_carlo=monte_carlo_summary,
            data_quality=_data_quality(metadata),
            artifact_path=artifact_path,
            warnings=backtest.get("warnings", []),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "research_error")
    except RuntimeError as exc:
        return _error_response(str(exc), ["runtime_error"])
    except Exception as exc:
        return _unexpected_error_response("strategy research", exc)


@mcp.tool()
@traced_tool()
def run_markowitz_optimization(
    symbols: list[str] | None = None,
    sector: str | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    objective: str = "max_sharpe",
    risk_free_rate: float = 0.0,
    allow_short: bool = False,
    max_weight: float = 0.6,
    num_frontier_portfolios: int = 3000,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Run Markowitz mean-variance portfolio optimization for selected US stocks."""
    try:
        return run_markowitz_optimization_core(
            symbols=symbols,
            sector=sector,
            lookback=lookback,
            resolution=resolution,
            objective=objective,
            risk_free_rate=risk_free_rate,
            allow_short=allow_short,
            max_weight=max_weight,
            num_frontier_portfolios=num_frontier_portfolios,
            finnhub_api_key=finnhub_api_key,
        )
    except ValueError as exc:
        return _value_error_response(exc, "markowitz_error")
    except RuntimeError as exc:
        return _error_response(str(exc), ["runtime_error"])
    except Exception as exc:
        return _unexpected_error_response("portfolio optimization", exc)


async def _health(_request):
    return JSONResponse({"status": "ok", "server": "VectorBT Standalone Strategy Server"})


async def _artifact(request):
    artifact_id = str(request.path_params.get("artifact_id", ""))
    name = Path(artifact_id).name
    if not name or name != artifact_id:
        return JSONResponse({"status": "error", "message": "Invalid artifact id."}, status_code=400)
    if not name.endswith(".json"):
        name = f"{name}.json"

    results_dir = cache_dir("results").resolve()
    artifact_path = (results_dir / name).resolve()
    try:
        artifact_path.relative_to(results_dir)
    except ValueError:
        return JSONResponse({"status": "error", "message": "Invalid artifact id."}, status_code=400)

    if not artifact_path.exists():
        return JSONResponse({"status": "error", "message": "Artifact not found."}, status_code=404)
    return FileResponse(artifact_path, media_type="application/json")


def _transport() -> str:
    return (os.getenv("MCP_TRANSPORT", "stdio") or "stdio").strip().lower().replace("_", "-")


def _run_http_app(transport: str) -> None:
    import uvicorn

    app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()
    configure_langsmith_middleware(app)
    app.add_route("/health", _health, methods=["GET"])
    app.add_route(f"{MCP_PROXY_PREFIX}/health", _health, methods=["GET"])
    app.add_route("/artifacts/{artifact_id}", _artifact, methods=["GET"])
    app.add_route(f"{MCP_PROXY_PREFIX}/artifacts/{{artifact_id}}", _artifact, methods=["GET"])
    uvicorn.run(app, host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)


if __name__ == "__main__":
    transport = _transport()
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport in {"streamable-http", "sse"}:
        _run_http_app(transport)
    else:
        raise SystemExit(f"Unsupported MCP_TRANSPORT: {transport}")
