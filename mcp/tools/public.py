from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.errors import exception_response
from services.artifacts import ArtifactService
from services.market_data import MarketDataService
from services.monte_carlo_engine import MonteCarloEngine
from services.persistence import PersistenceService
from services.portfolio_optimizer import PortfolioOptimizer
from services.ui_spec_builder import UISpecBuilder
from services.vectorbt_engine import VectorBTEngine
from schemas.results import ResearchResultEnvelope
from schemas.workflows import MonteCarloSettings, OptimizationSettings
from tools.universe import resolve_symbols_for_sector, validate_symbols
from workflows.discovery import DiscoveryWorkflow
from workflows.multi_stock import MultiStockResearchWorkflow
from workflows.registry_search import RegistrySearchWorkflow
from workflows.single_stock import SingleStockResearchWorkflow
from workflows.strategy_comparison import StrategyComparisonWorkflow


def search_strategy_registry(
    query: str | None = None,
    family: str | None = None,
    readiness: str | None = None,
    execution_type: str | None = None,
    executable_only: bool = False,
    limit: int = 25,
) -> dict[str, Any]:
    try:
        payload = {
            "query": query,
            "family": family,
            "readiness": readiness,
            "execution_type": execution_type,
            "executable_only": executable_only,
            "limit": limit,
        }
        return RegistrySearchWorkflow().search({key: value for key, value in payload.items() if value is not None})
    except Exception as exc:
        return exception_response("strategy registry search", exc)


def get_strategy_details(strategy_id: str) -> dict[str, Any]:
    try:
        return RegistrySearchWorkflow().details({"strategy_id": strategy_id})
    except Exception as exc:
        return exception_response("strategy detail lookup", exc)


def run_single_stock_research(
    symbol: str,
    strategy_id: str,
    parameters: dict[str, Any] | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    initial_cash: float = 10000,
    fees: float = 0.001,
    monte_carlo: dict[str, Any] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    try:
        return SingleStockResearchWorkflow().run(
            {
                "symbol": symbol,
                "strategy_id": strategy_id,
                "parameters": parameters or {},
                "lookback": lookback,
                "resolution": resolution,
                "initial_cash": initial_cash,
                "fees": fees,
                "monte_carlo": monte_carlo or {},
                "finnhub_api_key": finnhub_api_key,
            }
        )
    except Exception as exc:
        return exception_response("single-stock research", exc)


def run_multi_stock_research(
    symbols: list[str],
    strategy_id: str,
    parameters: dict[str, Any] | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    initial_cash: float = 10000,
    fees: float = 0.001,
    optimization: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    try:
        return MultiStockResearchWorkflow().run(
            {
                "symbols": symbols,
                "strategy_id": strategy_id,
                "parameters": parameters or {},
                "lookback": lookback,
                "resolution": resolution,
                "initial_cash": initial_cash,
                "fees": fees,
                "optimization": optimization or {},
                "monte_carlo": monte_carlo or {"enabled": True, "mode": "portfolio_returns"},
                "finnhub_api_key": finnhub_api_key,
            }
        )
    except Exception as exc:
        return exception_response("multi-stock research", exc)


def run_raw_markowitz_optimization(
    symbols: list[str] | None = None,
    sector: str | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    initial_cash: float = 10000,
    fees: float = 0.001,
    optimization: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Optimize a raw-asset portfolio from historical asset returns."""
    try:
        import uuid

        run_id = f"raw_markowitz_{uuid.uuid4().hex[:8]}"
        requested_sector = str(sector or "").strip() or None
        requested_symbols = _normalize_symbols(symbols or [])
        if not requested_symbols and requested_sector:
            requested_symbols = resolve_symbols_for_sector(requested_sector)
        if len(requested_symbols) < 2:
            raise ValueError("Provide at least two symbols or a sector with at least two stocks.")

        used_symbols = validate_symbols(requested_symbols) or requested_symbols
        if len(used_symbols) < 2:
            raise ValueError("At least two valid symbols are required for raw Markowitz optimization.")

        optimizer_settings = OptimizationSettings.model_validate(optimization or {})
        mc_settings = MonteCarloSettings.model_validate(
            {"mode": "raw_asset_returns", **(monte_carlo or {})}
        )
        market_data = MarketDataService()
        close_prices = market_data.fetch_aligned_closes(
            used_symbols,
            lookback=lookback,
            resolution=resolution,
            finnhub_api_key=finnhub_api_key,
        )
        returns = close_prices.pct_change(fill_method=None).replace([float("inf"), float("-inf")], None).dropna(how="any")
        optimization_result = PortfolioOptimizer().optimize_returns(returns, optimizer_settings)
        portfolio_backtest = VectorBTEngine().run_weighted_portfolio_backtest(
            returns,
            optimization_result["weights"],
            initial_cash=initial_cash,
        )
        mc_result = None
        if mc_settings.enabled:
            mc_result = MonteCarloEngine().simulate_returns(
                portfolio_backtest["returns"],
                start_value=float(portfolio_backtest["metrics"]["final_value"]),
                settings=mc_settings,
            )

        artifact_payload = {
            "run_id": run_id,
            "mode": "raw_asset_markowitz",
            "symbols": list(returns.columns),
            "sector": requested_sector,
            "lookback": lookback,
            "resolution": resolution,
            "initial_cash": initial_cash,
            "fees": fees,
            "optimization": optimization_result,
            "optimizer_settings": optimizer_settings.model_dump(mode="json"),
            "portfolio_backtest": {key: value for key, value in portfolio_backtest.items() if key != "returns"},
            "portfolio_returns": portfolio_backtest["returns"],
            "monte_carlo": mc_result,
        }
        artifact = ArtifactService().save_json(run_id, artifact_payload, artifact_type="raw_markowitz")
        envelope = ResearchResultEnvelope(
            status="success",
            workflow_type="raw_asset_markowitz",
            run_id=run_id,
            strategy={"strategy_id": None, "name": "Raw Asset Markowitz", "execution_type": "raw_asset_returns"},
            universe={"symbols": list(returns.columns), "sector": requested_sector},
            parameters={
                "lookback": lookback,
                "resolution": resolution,
                "initial_cash": initial_cash,
                "fees": fees,
                "optimizer": optimizer_settings.model_dump(mode="json"),
                "monte_carlo": mc_settings.model_dump(mode="json"),
            },
            data_quality={
                "symbols_requested": len(requested_symbols),
                "symbols_used": len(returns.columns),
                "start_date": returns.index[0].date().isoformat(),
                "end_date": returns.index[-1].date().isoformat(),
                "rows_used": int(len(returns)),
            },
            summary={
                "mode": "Raw Asset Markowitz",
                "symbols": list(returns.columns),
                "final_value": portfolio_backtest["metrics"].get("final_value"),
                "total_return_pct": portfolio_backtest["metrics"].get("total_return_pct"),
            },
            metrics=portfolio_backtest["metrics"],
            allocations={"weights": optimization_result["weights"], "optimizer_metrics": optimization_result["metrics"]},
            equity=portfolio_backtest.get("equity_curve", [])[:500],
            drawdown=portfolio_backtest.get("drawdown_curve", [])[:500],
            monte_carlo=mc_result,
            frontier=optimization_result.get("frontier", [])[:300],
            warnings=optimization_result.get("warnings", []),
            artifacts=[artifact],
            ui_hint="optimized_multi_stock_portfolio",
            diagnostics={
                "optimizer_input": "raw_asset_returns",
                "monte_carlo_input": "optimized_raw_asset_portfolio_returns" if mc_result else None,
                "correlation_matrix": optimization_result.get("correlation_matrix", []),
                "min_volatility_portfolio": optimization_result.get("min_volatility_portfolio"),
                "max_sharpe_portfolio": optimization_result.get("max_sharpe_portfolio"),
            },
        )
        envelope.ui_spec = UISpecBuilder().build_for_envelope(envelope)
        envelope.persistence = PersistenceService().persist_research_result(envelope)
        return envelope.model_dump(mode="json", exclude_none=True)
    except Exception as exc:
        return exception_response("raw Markowitz optimization", exc)


def run_raw_asset_monte_carlo(
    symbol: str,
    lookback: str = "2y",
    resolution: str = "D",
    start_value: float = 10000,
    monte_carlo: dict[str, Any] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    """Run explicit standalone Monte Carlo from one raw asset return stream."""
    try:
        import uuid

        settings = MonteCarloSettings.model_validate(
            {"mode": "raw_asset_returns", **(monte_carlo or {})}
        )
        df, metadata = MarketDataService().fetch_symbol(
            symbol,
            lookback=lookback,
            resolution=resolution,
            finnhub_api_key=finnhub_api_key,
        )
        returns = df["close"].astype(float).pct_change(fill_method=None).replace(
            [float("inf"), float("-inf")],
            None,
        ).dropna()
        result = MonteCarloEngine().simulate_returns(
            returns,
            start_value=start_value,
            settings=settings,
        )
        run_id = f"raw_mc_{uuid.uuid4().hex[:8]}"
        artifact = ArtifactService().save_json(
            run_id,
            {
                "run_id": run_id,
                "symbol": metadata["symbol"],
                "mode": "raw_asset_returns",
                "lookback": lookback,
                "resolution": resolution,
                "start_value": start_value,
                "monte_carlo": result,
                "data_quality": MarketDataService.data_quality(metadata),
            },
            artifact_type="raw_asset_monte_carlo",
        )
        envelope = ResearchResultEnvelope(
            status="success",
            workflow_type="raw_asset_monte_carlo",
            run_id=run_id,
            strategy={"strategy_id": None, "name": "Standalone Raw Asset Monte Carlo"},
            universe={"symbols": [metadata["symbol"]]},
            parameters={
                "lookback": lookback,
                "resolution": resolution,
                "start_value": start_value,
                "monte_carlo": settings.model_dump(mode="json"),
            },
            data_quality=MarketDataService.data_quality(metadata),
            summary=result.get("summary", {}),
            monte_carlo=result,
            artifacts=[artifact],
            ui_hint="monte_carlo_deep_dive",
            diagnostics={"monte_carlo_input": "raw_asset_returns"},
        )
        envelope.ui_spec = UISpecBuilder().build_for_envelope(envelope)
        envelope.persistence = PersistenceService().persist_research_result(envelope)
        return envelope.model_dump(mode="json", exclude_none=True)
    except Exception as exc:
        return exception_response("raw asset Monte Carlo", exc)


def compare_strategies(
    symbol: str,
    strategy_ids: list[str],
    parameters_by_strategy: dict[str, dict[str, Any]] | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    initial_cash: float = 10000,
    fees: float = 0.001,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    try:
        return StrategyComparisonWorkflow().run(
            {
                "symbol": symbol,
                "strategy_ids": strategy_ids,
                "parameters_by_strategy": parameters_by_strategy or {},
                "lookback": lookback,
                "resolution": resolution,
                "initial_cash": initial_cash,
                "fees": fees,
                "finnhub_api_key": finnhub_api_key,
            }
        )
    except Exception as exc:
        return exception_response("strategy comparison", exc)


def discover_strategy_candidates(
    query: str,
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
    max_candidates: int = 20,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    try:
        return DiscoveryWorkflow().discover(
            {
                "query": query,
                "sources": sources or ["openalex", "crossref", "arxiv"],
                "max_results_per_source": max_results_per_source,
                "max_candidates": max_candidates,
                "start_year": start_year,
                "end_year": end_year,
            }
        )
    except Exception as exc:
        return exception_response("strategy discovery", exc)


def review_strategy_candidate(
    candidate_id: str,
    action: str,
    reviewer: str | None = None,
    reviewer_note: str = "",
    edits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        return DiscoveryWorkflow().review(
            {
                "candidate_id": candidate_id,
                "action": action,
                "reviewer": reviewer,
                "reviewer_note": reviewer_note,
                "edits": edits or {},
            }
        )
    except Exception as exc:
        return exception_response("strategy candidate review", exc)


def process_approved_strategy(candidate_id: str, limit: int = 1) -> dict[str, Any]:
    try:
        return DiscoveryWorkflow().process_approved({"candidate_id": candidate_id, "limit": limit})
    except Exception as exc:
        return exception_response("approved strategy processing", exc)


def get_research_run(run_id: str) -> dict[str, Any]:
    try:
        result = PersistenceService().get_research_run(run_id)
        if result is None:
            return {"status": "error", "message": "Research run not found.", "errors": ["run_not_found"]}
        return {"status": "success", "run": result}
    except Exception as exc:
        return exception_response("research run lookup", exc)


def list_research_runs(limit: int = 25) -> dict[str, Any]:
    try:
        return {"status": "success", "runs": PersistenceService().list_research_runs(limit=limit)}
    except Exception as exc:
        return exception_response("research run listing", exc)


def get_artifact_summary(artifact_id: str) -> dict[str, Any]:
    try:
        artifact = ArtifactService()
        return {
            "status": "success",
            "artifact_id": artifact_id,
            "summary": {
                "message": "Artifact summaries are available in research run artifact references.",
            },
        }
    except Exception as exc:
        return exception_response("artifact summary", exc)


def sync_strategy_registry() -> dict[str, Any]:
    try:
        return RegistrySearchWorkflow().sync_import()
    except Exception as exc:
        return exception_response("strategy registry sync", exc)


def register_public_tools(mcp: FastMCP) -> None:
    mcp.tool()(search_strategy_registry)
    mcp.tool()(get_strategy_details)
    mcp.tool()(run_single_stock_research)
    mcp.tool()(run_multi_stock_research)
    mcp.tool()(run_raw_markowitz_optimization)
    mcp.tool()(run_raw_asset_monte_carlo)
    mcp.tool()(compare_strategies)
    mcp.tool()(discover_strategy_candidates)
    mcp.tool()(review_strategy_candidate)
    mcp.tool()(process_approved_strategy)
    mcp.tool()(get_research_run)
    mcp.tool()(list_research_runs)
    mcp.tool()(get_artifact_summary)
    mcp.tool()(sync_strategy_registry)


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        cleaned = str(symbol or "").strip().upper()
        if ":" in cleaned:
            cleaned = cleaned.split(":")[-1]
        if cleaned and cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)
    return normalized
