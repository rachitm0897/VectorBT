from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import persist_backtest_analytics_async
from apps.backtesting.engine import BacktestExecutionError, run_backtest
from apps.backtesting.serializers import BacktestRequestSerializer
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

        try:
            result = run_backtest(serializer.validated_data)
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

        persist_backtest_analytics_async(
            {**result, "_analytics_request": dict(serializer.validated_data)},
            source="backtest_api",
        )
        return Response(result, status=status.HTTP_200_OK)


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
