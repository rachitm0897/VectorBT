import json

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_keys import api_keys_from_request
from apps.agent.graph import run_chat_workflow
from apps.agent.serializers import ChatRequestSerializer


class ChatAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "assistant_message": "Invalid chat request.",
                    "parsed_request": {},
                    "result_type": "",
                    "backtest_result": {},
                    "portfolio_result": {},
                    "errors": _serializer_errors(serializer.errors),
                    "missing_fields": [],
                    "warnings": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_keys = api_keys_from_request(request)
        result = run_chat_workflow(
            serializer.validated_data["message"],
            chat_url=api_keys.chat_url,
            chat_api_key=api_keys.chat_api_key,
            model=api_keys.model,
            finnhub_api_key=api_keys.finnhub_api_key,
            request_id=request.headers.get("X-Request-ID"),
        )
        response_status = status.HTTP_200_OK
        if result["status"] == "error":
            response_status = status.HTTP_400_BAD_REQUEST
        return Response(result, status=response_status)


class ChatStreamAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return StreamingHttpResponse(
                _single_error_event("Invalid chat request.", _serializer_errors(serializer.errors)),
                content_type="text/event-stream",
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_keys = api_keys_from_request(request)

        def event_stream():
            yield _sse("workflow.started", {"workflow_type": "research_chat"})
            yield _sse("message.delta", {"content": "Parsing request."})
            yield _sse("tool.started", {"tool": "chat_intent_router"})
            result = run_chat_workflow(
                serializer.validated_data["message"],
                chat_url=api_keys.chat_url,
                chat_api_key=api_keys.chat_api_key,
                model=api_keys.model,
                finnhub_api_key=api_keys.finnhub_api_key,
                request_id=request.headers.get("X-Request-ID"),
            )
            if result.get("status") == "error":
                yield _sse("error", {"message": result.get("assistant_message"), "errors": result.get("errors", [])})
            else:
                yield _sse("tool.completed", {"result_type": result.get("result_type"), "status": result.get("status")})
                run_id = _linked_run_id(result)
                if run_id:
                    yield _sse("artifact.ready", {"run_id": run_id})
                yield _sse("ui.spec", _ui_spec_from_chat_result(result))
                yield _sse("message.delta", {"content": result.get("assistant_message", "")})
                yield _sse("message.completed", result)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


def _serializer_errors(errors) -> list[str]:
    return [f"{field}: {message}" for field, messages in errors.items() for message in messages]


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _single_error_event(message: str, errors: list[str]):
    yield _sse("error", {"message": message, "errors": errors})


def _linked_run_id(result: dict) -> str | None:
    for key in ("backtest_result", "portfolio_result", "factor_portfolio_result"):
        value = result.get(key)
        if isinstance(value, dict):
            diagnostics = value.get("diagnostics") if isinstance(value.get("diagnostics"), dict) else {}
            mcp = diagnostics.get("mcp") if isinstance(diagnostics.get("mcp"), dict) else {}
            run_id = value.get("run_id") or mcp.get("run_id") or value.get("artifact_id")
            if run_id:
                return str(run_id)
    return None


def _ui_spec_from_chat_result(result: dict) -> dict:
    result_type = result.get("result_type") or "strategy_backtest"
    template_id = {
        "portfolio_optimization": "optimized_multi_stock_portfolio",
        "factor_portfolio": "universe_backtest_classification",
        "strategy_backtest": "single_stock_research",
    }.get(str(result_type), "single_stock_research")
    return {
        "template_id": template_id,
        "props": {
            "result_type": result_type,
            "parsed_request": result.get("parsed_request") or {},
            "run_id": _linked_run_id(result),
        },
    }
