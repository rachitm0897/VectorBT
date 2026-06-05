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


def _serializer_errors(errors) -> list[str]:
    return [f"{field}: {message}" for field, messages in errors.items() for message in messages]
