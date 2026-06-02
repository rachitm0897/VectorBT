from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import persist_backtest_analytics_async
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


def _serializer_errors(errors) -> list[str]:
    return [f"{field}: {message}" for field, messages in errors.items() for message in messages]
