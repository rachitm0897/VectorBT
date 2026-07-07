from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from tools.backtesting import run_vectorbt_backtest
from tools.factor_scoring import construct_factor_portfolio_core
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
    FactorPortfolioRequest,
    IndicatorBatchRequest,
    IndicatorRequest,
    MarkowitzOptimizationRequest,
    MarketDataRequest,
    MonteCarloRequest,
    StrategyBacktestRequest,
    StrategyResearchRequest,
    model_to_dict,
    parse_request,
)
from tools.strategies import generate_strategy_signals, list_strategy_definitions, strategy_schema
from tools.talib_adapter import (
    compute_talib_indicator,
    get_talib_indicator_info,
    list_talib_indicators,
)
from tools.tracing import get_request_id, traced_tool
from tools.universe import (
    list_all_stocks as universe_list_all_stocks,
    list_sectors as universe_list_sectors,
    list_stocks_by_sector as universe_list_stocks_by_sector,
    resolve_symbols_for_sector as universe_resolve_symbols_for_sector,
)

logger = logging.getLogger("vectorbt_mcp.legacy")


def _error_response(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    return {"status": "error", "message": message, "errors": errors or ["unknown_error"]}


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


def _serialize_indicator_outputs(outputs: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
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


@traced_tool()
def list_strategies() -> dict[str, Any]:
    """List supported prototype trading strategies."""
    return {"status": "success", "strategies": list_strategy_definitions()}


@traced_tool()
def get_strategy_schema(strategy: str) -> dict[str, Any]:
    """Return the parameter schema for a supported strategy."""
    try:
        return {"status": "success", "strategy": strategy, "parameters": strategy_schema(strategy)}
    except ValueError as exc:
        return _error_response(str(exc), ["unsupported_strategy"])


@traced_tool()
def list_indicators() -> dict[str, Any]:
    """List TA-Lib indicators available through the finance indicator workflow."""
    return {"status": "success", "indicators": list_talib_indicators()}


@traced_tool()
def get_indicator_info(indicator: str) -> dict[str, Any]:
    """Return TA-Lib metadata for one indicator."""
    try:
        normalized = str(indicator or "").strip().upper()
        return {"status": "success", "indicator": normalized, "info": get_talib_indicator_info(normalized)}
    except ValueError as exc:
        return _error_response(str(exc), ["unsupported_indicator"])


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
                error = {"indicator": normalized, "message": str(exc)}
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
        return {"status": "success", "count": len(stocks), "sector": requested_sector, "stocks": stocks}
    except FileNotFoundError as exc:
        return _error_response(str(exc), ["universe_file_missing"])
    except Exception as exc:
        return _unexpected_error_response("stock universe loading", exc)


@traced_tool()
def list_sectors() -> dict[str, Any]:
    """List sectors found in the US stock universe."""
    try:
        return {"status": "success", "sectors": universe_list_sectors()}
    except FileNotFoundError as exc:
        return _error_response(str(exc), ["universe_file_missing"])
    except Exception as exc:
        return _unexpected_error_response("sector loading", exc)


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


@traced_tool()
def resolve_symbols_for_sector(sector: str) -> dict[str, Any]:
    """Resolve all ticker symbols for a sector in the US stock universe."""
    try:
        symbols = universe_resolve_symbols_for_sector(sector)
        return {"status": "success", "sector": sector, "symbols": symbols, "count": len(symbols)}
    except FileNotFoundError as exc:
        return _error_response(str(exc), ["universe_file_missing"])
    except Exception as exc:
        return _unexpected_error_response("sector symbol resolution", exc)


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
    """Run a legacy raw-asset bootstrap Monte Carlo simulation and return a compact summary."""
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
            "mode": "raw_asset_returns",
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
    """Run the legacy compact research workflow for one symbol and strategy."""
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
            equity = [point.get("value") for point in backtest.get("equity_curve", []) if isinstance(point, dict)]
            simulation = run_bootstrap_monte_carlo(
                equity,
                start_value=backtest["metrics"]["final_value"],
                days=request.monte_carlo_days,
                simulations=request.monte_carlo_simulations,
            )
            artifact["monte_carlo"] = simulation
            artifact["monte_carlo_input"] = "strategy_equity_returns"
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
    run_monte_carlo: bool = False,
    monte_carlo_days: int = 60,
    monte_carlo_simulations: int = 500,
    monte_carlo_block_size: int = 5,
    monte_carlo_seed: int | None = 42,
    monte_carlo_scenarios: list[str] | None = None,
    scenario_overrides: dict[str, Any] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Run legacy raw-asset Markowitz mean-variance portfolio optimization."""
    try:
        request = parse_request(
            MarkowitzOptimizationRequest,
            {
                "symbols": symbols,
                "sector": sector,
                "lookback": lookback,
                "resolution": resolution,
                "objective": objective,
                "risk_free_rate": risk_free_rate,
                "allow_short": allow_short,
                "max_weight": max_weight,
                "num_frontier_portfolios": num_frontier_portfolios,
                "run_monte_carlo": run_monte_carlo,
                "monte_carlo_days": monte_carlo_days,
                "monte_carlo_simulations": monte_carlo_simulations,
                "monte_carlo_block_size": monte_carlo_block_size,
                "monte_carlo_seed": monte_carlo_seed,
                "monte_carlo_scenarios": monte_carlo_scenarios or ["neutral", "bullish", "bearish", "crash"],
                "scenario_overrides": scenario_overrides or {},
                "finnhub_api_key": finnhub_api_key,
            },
        )
        return run_markowitz_optimization_core(
            symbols=request.symbols,
            sector=request.sector,
            lookback=request.lookback,
            resolution=request.resolution,
            objective=request.objective,
            risk_free_rate=request.risk_free_rate,
            allow_short=request.allow_short,
            max_weight=request.max_weight,
            num_frontier_portfolios=request.num_frontier_portfolios,
            run_monte_carlo=request.run_monte_carlo,
            monte_carlo_days=request.monte_carlo_days,
            monte_carlo_simulations=request.monte_carlo_simulations,
            monte_carlo_block_size=request.monte_carlo_block_size,
            monte_carlo_seed=request.monte_carlo_seed,
            monte_carlo_scenarios=list(request.monte_carlo_scenarios),
            scenario_overrides={
                name: _scenario_override_dict(override)
                for name, override in request.scenario_overrides.items()
            },
            finnhub_api_key=request.finnhub_api_key,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "markowitz_error")
    except RuntimeError as exc:
        return _error_response(str(exc), ["runtime_error"])
    except Exception as exc:
        return _unexpected_error_response("portfolio optimization", exc)


@traced_tool()
def construct_factor_portfolio(
    symbols: list[str] | None = None,
    sector: str | None = None,
    selection_mode: str = "symbols",
    lookback: str = "2y",
    resolution: str = "D",
    factor_model: dict[str, Any] | None = None,
    optimization: dict[str, Any] | None = None,
    score_tilt: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Construct a factor-ranked portfolio, then run Markowitz optimization and scenarios."""
    try:
        request = parse_request(
            FactorPortfolioRequest,
            {
                "symbols": symbols,
                "sector": sector,
                "selection_mode": selection_mode,
                "lookback": lookback,
                "resolution": resolution,
                "factor_model": factor_model or {},
                "optimization": optimization or {},
                "score_tilt": score_tilt or {},
                "monte_carlo": monte_carlo or {},
                "finnhub_api_key": finnhub_api_key,
            },
        )
        return construct_factor_portfolio_core(
            symbols=request.symbols,
            sector=request.sector,
            selection_mode=request.selection_mode,
            lookback=request.lookback,
            resolution=request.resolution,
            factor_model=model_to_dict(request.factor_model),
            optimization=model_to_dict(request.optimization),
            score_tilt=model_to_dict(request.score_tilt),
            monte_carlo=model_to_dict(request.monte_carlo),
            finnhub_api_key=request.finnhub_api_key,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    except ValueError as exc:
        return _value_error_response(exc, "factor_portfolio_error")
    except RuntimeError as exc:
        return _error_response(str(exc), ["runtime_error"])
    except Exception as exc:
        return _unexpected_error_response("factor portfolio construction", exc)


def _scenario_override_dict(override: Any) -> dict[str, Any]:
    if hasattr(override, "model_dump"):
        data = override.model_dump()
    elif hasattr(override, "dict"):
        data = override.dict()
    else:
        data = dict(override or {})
    return {key: value for key, value in data.items() if value is not None}


def register_legacy_tools(mcp: FastMCP) -> None:
    for func in (
        list_strategies,
        get_strategy_schema,
        list_indicators,
        get_indicator_info,
        compute_indicator,
        compute_indicators_batch,
        list_stock_universe,
        list_sectors,
        list_stocks_by_sector,
        resolve_symbols_for_sector,
        fetch_market_data_summary,
        run_strategy_backtest,
        run_monte_carlo_simulation,
        run_strategy_research,
        run_markowitz_optimization,
        construct_factor_portfolio,
    ):
        mcp.tool()(func)


def artifact_path_from_id(artifact_id: str, results_dir: Path) -> Path:
    name = Path(artifact_id).name
    if not name.endswith(".json"):
        name = f"{name}.json"
    return (results_dir / name).resolve()
