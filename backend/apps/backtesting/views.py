from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_keys import api_keys_from_request
from apps.backtesting.mcp_client import (
    MCPClientError,
    fetch_remote_sectors,
    fetch_remote_stocks_by_sector,
    get_remote_research_run,
    get_mcp_status,
    list_remote_research_runs,
    resolve_remote_sector_symbols,
    run_remote_raw_asset_monte_carlo,
    run_remote_raw_markowitz_research,
    run_remote_multi_stock_research,
    run_remote_single_stock_research,
)
from apps.analytics.services import analytics_status
from apps.backtesting.engine import BacktestExecutionError, run_backtest, run_portfolio_optimization
from apps.backtesting.engine import run_factor_portfolio
from apps.backtesting.serializers import (
    BacktestRequestSerializer,
    FactorPortfolioRequestSerializer,
    MultiStockResearchRequestSerializer,
    PortfolioOptimizationRequestSerializer,
    RawMonteCarloRequestSerializer,
    SingleStockResearchRequestSerializer,
)
from apps.market_data.finnhub import MarketDataError
from apps.strategies.registry import StrategyValidationError


class BacktestAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = BacktestRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Invalid backtest request.",
                    "errors": _serializer_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_keys = api_keys_from_request(request)

        try:
            result = run_backtest(serializer.validated_data, finnhub_api_key=api_keys.finnhub_api_key)
        except MarketDataError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)
        except StrategyValidationError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_400_BAD_REQUEST)
        except BacktestExecutionError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_400_BAD_REQUEST)
        except Exception:
            return _error_response(
                "Backtest failed unexpectedly.",
                "backtest_failed",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class MCPStatusAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request):
        return Response(get_mcp_status(), status=status.HTTP_200_OK)


class PortfolioOptimizeAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = PortfolioOptimizationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "assistant_message": "Invalid portfolio optimization request.",
                    "parsed_request": {},
                    "portfolio_result": {},
                    "errors": _serializer_errors(serializer.errors),
                    "warnings": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_keys = api_keys_from_request(request)
        try:
            result = run_portfolio_optimization(
                serializer.validated_data,
                finnhub_api_key=api_keys.finnhub_api_key,
            )
        except BacktestExecutionError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_400_BAD_REQUEST)
        except Exception:
            return _error_response(
                "Portfolio optimization failed unexpectedly.",
                "portfolio_optimization_failed",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class FactorPortfolioAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = FactorPortfolioRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "assistant_message": "Invalid factor portfolio request.",
                    "parsed_request": {},
                    "factor_portfolio_result": {},
                    "errors": _serializer_errors(serializer.errors),
                    "warnings": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_keys = api_keys_from_request(request)
        try:
            result = run_factor_portfolio(
                serializer.validated_data,
                finnhub_api_key=api_keys.finnhub_api_key,
            )
        except BacktestExecutionError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_400_BAD_REQUEST)
        except Exception:
            return _error_response(
                "Factor portfolio construction failed unexpectedly.",
                "factor_portfolio_failed",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class SingleStockResearchAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = SingleStockResearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Invalid single-stock research request.",
                    "errors": _serializer_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        api_keys = api_keys_from_request(request)
        try:
            result = run_remote_single_stock_research(
                serializer.validated_data,
                finnhub_api_key=api_keys.finnhub_api_key,
            )
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)
        return Response(result, status=status.HTTP_200_OK)


class MultiStockResearchAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = MultiStockResearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Invalid multi-stock research request.",
                    "errors": _serializer_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        api_keys = api_keys_from_request(request)
        try:
            result = run_remote_multi_stock_research(
                serializer.validated_data,
                finnhub_api_key=api_keys.finnhub_api_key,
            )
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)
        return Response(result, status=status.HTTP_200_OK)


class RawMarkowitzResearchAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = PortfolioOptimizationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Invalid raw Markowitz request.",
                    "errors": _serializer_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        api_keys = api_keys_from_request(request)
        try:
            result = run_remote_raw_markowitz_research(
                serializer.validated_data,
                finnhub_api_key=api_keys.finnhub_api_key,
            )
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)
        return Response(result, status=status.HTTP_200_OK)


class RawAssetMonteCarloAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RawMonteCarloRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Invalid raw asset Monte Carlo request.",
                    "errors": _serializer_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        api_keys = api_keys_from_request(request)
        try:
            result = run_remote_raw_asset_monte_carlo(
                serializer.validated_data,
                finnhub_api_key=api_keys.finnhub_api_key,
            )
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)
        return Response(result, status=status.HTTP_200_OK)


class ResearchRunsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 25))
            return Response(list_remote_research_runs(limit=limit), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


class ResearchRunDetailsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request, run_id: str):
        try:
            return Response(get_remote_research_run(run_id), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


class UniverseSectorsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            return Response(fetch_remote_sectors(), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)
        except Exception:
            return _error_response(
                "Could not load universe sectors.",
                "universe_sectors_failed",
                status.HTTP_502_BAD_GATEWAY,
            )


class UniverseStocksAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        sector = str(request.query_params.get("sector") or "").strip()
        try:
            return Response(fetch_remote_stocks_by_sector(sector or None), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)
        except Exception:
            return _error_response(
                "Could not load universe stocks.",
                "universe_stocks_failed",
                status.HTTP_502_BAD_GATEWAY,
            )


class UniverseResolveSymbolsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        sector = str(request.query_params.get("sector") or "").strip()
        if not sector:
            return _error_response("sector is required.", "missing_sector", status.HTTP_400_BAD_REQUEST)
        try:
            return Response(resolve_remote_sector_symbols(sector), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


class SystemHealthAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request):
        mcp = get_mcp_status()
        analytics = analytics_status()
        registry_summary = {}
        if mcp.get("connected"):
            try:
                from apps.backtesting.mcp_client import search_remote_strategy_registry

                registry_summary = (search_remote_strategy_registry(limit=1).get("summary") or {})
            except Exception as exc:
                registry_summary = {"error": str(exc)}
        return Response(
            {
                "status": "success",
                "backend": {"status": "ok"},
                "mcp": mcp,
                "analytics": analytics,
                "metabase": {
                    "url": analytics.get("metabase_url"),
                    "status": "configured" if analytics.get("metabase_url") else "unknown",
                },
                "registry": registry_summary,
            },
            status=status.HTTP_200_OK,
        )


class MCPToolInventoryAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request):
        status_payload = get_mcp_status()
        available = set(status_payload.get("tools") or [])
        public_tools = [
            "search_strategy_registry",
            "get_strategy_details",
            "run_single_stock_research",
            "run_multi_stock_research",
            "run_raw_markowitz_optimization",
            "run_raw_asset_monte_carlo",
            "compare_strategies",
            "discover_strategy_candidates",
            "review_strategy_candidate",
            "process_approved_strategy",
            "get_research_run",
            "list_research_runs",
            "get_artifact_summary",
            "sync_strategy_registry",
        ]
        legacy_tools = [
            "list_strategies",
            "get_strategy_schema",
            "list_indicators",
            "get_indicator_info",
            "compute_indicator",
            "compute_indicators_batch",
            "list_stock_universe",
            "list_sectors",
            "list_stocks_by_sector",
            "resolve_symbols_for_sector",
            "fetch_market_data_summary",
            "run_strategy_backtest",
            "run_monte_carlo_simulation",
            "run_strategy_research",
            "run_markowitz_optimization",
            "construct_factor_portfolio",
        ]
        return Response(
            {
                "status": "success",
                "mcp": status_payload,
                "public_tools": [_tool_row(name, available) for name in public_tools],
                "legacy_tools": [_tool_row(name, available) for name in legacy_tools],
            },
            status=status.HTTP_200_OK,
        )


class SystemDiagnosticsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request):
        return Response(
            {
                "status": "success",
                "recent_mcp_calls": _recent_mcp_calls(),
                "recent_errors": _recent_mcp_errors(),
                "cache": _cache_status(),
                "artifacts": {"status": "served_by_mcp", "directory": "mcp/cache/results"},
                "database": analytics_status(),
            },
            status=status.HTTP_200_OK,
        )


def _error_response(message: str, code: str, response_status: int) -> Response:
    return Response(
        {
            "status": "error",
            "message": message,
            "errors": [code],
        },
        status=response_status,
    )


def _serializer_errors(errors) -> list[str]:
    flattened = []
    for field, messages in errors.items():
        if isinstance(messages, dict):
            for nested_field, nested_messages in messages.items():
                flattened.extend([f"{field}.{nested_field}: {message}" for message in nested_messages])
        else:
            flattened.extend([f"{field}: {message}" for message in messages])
    return flattened


def _tool_row(name: str, available: set[str]) -> dict:
    return {"name": name, "status": "available" if name in available else "not_reported"}


def _recent_mcp_calls() -> list[dict]:
    try:
        from apps.analytics.services import analytics_enabled, get_analytics_connection

        if not analytics_enabled():
            return []
        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tool_name, status, runtime_ms, request_type, symbol, strategy, sector, created_at
                    FROM mcp_tool_calls
                    ORDER BY created_at DESC
                    LIMIT 20
                    """
                )
                rows = cursor.fetchall()
        return [
            {
                "tool_name": row[0],
                "status": row[1],
                "runtime_ms": row[2],
                "request_type": row[3],
                "symbol": row[4],
                "strategy": row[5],
                "sector": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
            }
            for row in rows
        ]
    except Exception:
        return []


def _recent_mcp_errors() -> list[dict]:
    try:
        from apps.analytics.services import analytics_enabled, get_analytics_connection

        if not analytics_enabled():
            return []
        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tool_name, error_message, request_type, created_at
                    FROM mcp_tool_calls
                    WHERE status = 'error'
                    ORDER BY created_at DESC
                    LIMIT 20
                    """
                )
                rows = cursor.fetchall()
        return [
            {
                "tool_name": row[0],
                "message": row[1],
                "request_type": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]
    except Exception:
        return []


def _cache_status() -> dict:
    try:
        from django.conf import settings as django_settings

        market_dir = django_settings.MARKET_DATA_CACHE_DIR
        parsed_dir = django_settings.PARSED_REQUEST_CACHE_DIR
        return {
            "market_data_cache_dir": str(market_dir),
            "market_data_files": len(list(market_dir.glob("*"))) if market_dir.exists() else 0,
            "parsed_request_cache_dir": str(parsed_dir),
            "parsed_request_files": len(list(parsed_dir.glob("*"))) if parsed_dir.exists() else 0,
        }
    except Exception as exc:
        return {"error": str(exc)}
