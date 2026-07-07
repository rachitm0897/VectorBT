from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.errors import exception_response
from services.artifacts import ArtifactService
from services.persistence import PersistenceService
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
    mcp.tool()(compare_strategies)
    mcp.tool()(discover_strategy_candidates)
    mcp.tool()(review_strategy_candidate)
    mcp.tool()(process_approved_strategy)
    mcp.tool()(get_research_run)
    mcp.tool()(list_research_runs)
    mcp.tool()(get_artifact_summary)
    mcp.tool()(sync_strategy_registry)
