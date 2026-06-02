from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from tools.backtesting import run_vectorbt_backtest
from tools.formatting import (
    compact_backtest_response,
    compact_monte_carlo_response,
    compact_research_response,
    save_artifact_json,
    series_to_points,
)
from tools.market_data import fetch_finnhub_candles_with_metadata
from tools.monte_carlo import run_bootstrap_monte_carlo
from tools.schemas import (
    MarketDataRequest,
    MonteCarloRequest,
    StrategyBacktestRequest,
    StrategyResearchRequest,
    parse_request,
)
from tools.strategies import generate_strategy_signals, list_strategy_definitions, strategy_schema


SERVER_ROOT = Path(__file__).resolve().parent
load_dotenv(SERVER_ROOT / ".env")
load_dotenv()

mcp = FastMCP("VectorBT Standalone Strategy Server")


def _error_response(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "errors": errors or ["unknown_error"],
    }


def _validation_error_response(exc: ValidationError) -> dict[str, Any]:
    codes: list[str] = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err.get("loc", []))
        code = err.get("type", "validation_error")
        codes.append(f"{location}:{code}" if location else code)
    return _error_response("Invalid request parameters.", codes or ["validation_error"])


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


def _run_backtest_components(
    request: StrategyBacktestRequest | StrategyResearchRequest,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    df, metadata = fetch_finnhub_candles_with_metadata(
        request.symbol,
        lookback=request.lookback,
        resolution=request.resolution,
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
def list_strategies() -> dict[str, Any]:
    """List supported prototype trading strategies."""
    return {"status": "success", "strategies": list_strategy_definitions()}


@mcp.tool()
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
def fetch_market_data_summary(
    symbol: str,
    lookback: str = "2y",
    resolution: str = "D",
) -> dict[str, Any]:
    """Fetch Finnhub OHLCV data and return a compact data quality summary."""
    try:
        request = parse_request(
            MarketDataRequest,
            {"symbol": symbol, "lookback": lookback, "resolution": resolution},
        )
        _, metadata = fetch_finnhub_candles_with_metadata(
            request.symbol,
            lookback=request.lookback,
            resolution=request.resolution,
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
        return _error_response(str(exc), ["market_data_error"])
    except Exception:
        return _error_response("Unexpected error while fetching market data.", ["unexpected_error"])


@mcp.tool()
def run_strategy_backtest(
    symbol: str,
    strategy: str,
    parameters: dict[str, Any] | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    initial_cash: float | None = None,
    fees: float | None = None,
) -> dict[str, Any]:
    """Run one strategy backtest and return compact metrics plus an artifact path."""
    try:
        payload = {
            "symbol": symbol,
            "strategy": strategy,
            "parameters": parameters or {},
            "lookback": lookback,
            "resolution": resolution,
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
        return _error_response(str(exc), ["backtest_error"])
    except RuntimeError as exc:
        return _error_response(str(exc), ["runtime_error"])
    except Exception:
        return _error_response("Unexpected error while running the backtest.", ["unexpected_error"])


@mcp.tool()
def run_monte_carlo_simulation(
    symbol: str,
    lookback: str = "2y",
    resolution: str = "D",
    start_value: float = 10000,
    days: int = 60,
    simulations: int = 500,
    method: str = "bootstrap",
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
            },
        )
        df, metadata = fetch_finnhub_candles_with_metadata(
            request.symbol,
            lookback=request.lookback,
            resolution=request.resolution,
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
        return _error_response(str(exc), ["monte_carlo_error"])
    except Exception:
        return _error_response(
            "Unexpected error while running the Monte Carlo simulation.",
            ["unexpected_error"],
        )


@mcp.tool()
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
        return _error_response(str(exc), ["research_error"])
    except RuntimeError as exc:
        return _error_response(str(exc), ["runtime_error"])
    except Exception:
        return _error_response("Unexpected error while running strategy research.", ["unexpected_error"])


if __name__ == "__main__":
    mcp.run()
