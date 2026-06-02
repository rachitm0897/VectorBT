from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import persist_backtest_analytics_async
from apps.agent.graph import run_chat_workflow
from apps.agent.mcp_client.client import list_mcp_tools_sync
from apps.agent.mcp_client.errors import MCPClientError
from apps.agent.serializers import ChatRequestSerializer
from django.conf import settings


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
                    "backtest_result": {},
                    "errors": _serializer_errors(serializer.errors),
                    "missing_fields": [],
                    "warnings": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = run_chat_workflow(serializer.validated_data["message"])
        response_status = status.HTTP_200_OK
        if result["status"] == "error":
            response_status = status.HTTP_400_BAD_REQUEST
        elif result["status"] == "success" and isinstance(result.get("backtest_result"), dict):
            analytics_request = result.get("parsed_request") if isinstance(result.get("parsed_request"), dict) else {}
            persist_backtest_analytics_async(
                {**result["backtest_result"], "_analytics_request": analytics_request},
                source="chat_api",
            )
        return Response(result, status=response_status)


class MCPStatusAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        enabled = bool(settings.MCP_ENABLED)
        connected = False
        tools: list[str] = []
        error = None

        if enabled:
            try:
                tools = list_mcp_tools_sync()
                connected = True
            except MCPClientError as exc:
                error = exc.safe_message
            except Exception:
                error = "The MCP strategy server is unavailable."

        return Response(
            {
                "enabled": enabled,
                "transport": settings.MCP_TRANSPORT,
                "server_command": settings.MCP_SERVER_COMMAND,
                "server_args": settings.MCP_SERVER_ARGS,
                "connected": connected,
                "tools": tools,
                "error": error,
            }
        )


def _serializer_errors(errors) -> list[str]:
    return [f"{field}: {message}" for field, messages in errors.items() for message in messages]
