from __future__ import annotations

import os
from pathlib import Path

from starlette.responses import FileResponse, JSONResponse

from app.bootstrap import _env_int, _normalize_path, create_mcp_app
from tools.cache import cache_dir
from tools.legacy import (
    compute_indicator,
    compute_indicators_batch,
    construct_factor_portfolio,
    fetch_market_data_summary,
    get_indicator_info,
    get_strategy_schema,
    list_indicators,
    list_sectors,
    list_stock_universe,
    list_stocks_by_sector,
    list_strategies,
    resolve_symbols_for_sector,
    run_markowitz_optimization,
    run_monte_carlo_simulation,
    run_strategy_backtest,
    run_strategy_research,
)
from tools.public import (
    compare_strategies,
    discover_strategy_candidates,
    get_artifact_summary,
    get_research_run,
    get_strategy_details,
    list_research_runs,
    process_approved_strategy,
    review_strategy_candidate,
    run_multi_stock_research,
    run_single_stock_research,
    search_strategy_registry,
    sync_strategy_registry,
)
from tools.tracing import configure_langsmith_middleware


MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_SERVER_PORT = _env_int("MCP_SERVER_PORT", _env_int("PORT", 8001))
MCP_PROXY_PREFIX = _normalize_path(
    os.getenv("MCP_PROXY_PREFIX", "/insta_backtest_MCP_server"),
    "/insta_backtest_MCP_server",
)

mcp = create_mcp_app()


async def _health(_request):
    return JSONResponse({"status": "ok", "server": "VectorBT Quant Research MCP"})


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
