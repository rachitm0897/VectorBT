from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_keys import api_keys_from_request
from apps.backtesting.mcp_client import (
    MCPClientError,
    fetch_remote_sectors,
    fetch_remote_stocks_by_sector,
    get_mcp_status,
)
from apps.backtesting.engine import BacktestExecutionError, run_backtest, run_portfolio_optimization
from apps.backtesting.serializers import BacktestRequestSerializer, PortfolioOptimizationRequestSerializer
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
