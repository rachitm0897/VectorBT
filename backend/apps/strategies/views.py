from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.backtesting.mcp_client import (
    MCPClientError,
    discover_remote_strategy_candidates,
    get_remote_strategy_details,
    process_remote_approved_strategy,
    review_remote_strategy_candidate,
    search_remote_strategy_registry,
)


class StrategyRegistryAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            result = search_remote_strategy_registry(
                query=request.query_params.get("query"),
                family=request.query_params.get("family"),
                readiness=request.query_params.get("readiness"),
                execution_type=request.query_params.get("execution_type"),
                executable_only=str(request.query_params.get("executable_only", "false")).lower() == "true",
                limit=int(request.query_params.get("limit", 100)),
            )
            return Response(result, status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


class StrategyDetailsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request, strategy_id: str):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            return Response(get_remote_strategy_details(strategy_id), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


class StrategyDiscoveryAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        payload = {
            "query": str(request.data.get("query") or "").strip(),
            "sources": request.data.get("sources") or ["openalex", "crossref", "arxiv"],
            "max_results_per_source": int(request.data.get("max_results_per_source") or 10),
            "max_candidates": int(request.data.get("max_candidates") or 20),
            "start_year": request.data.get("start_year"),
            "end_year": request.data.get("end_year"),
        }
        if not payload["query"]:
            return _error_response("Discovery query is required.", "missing_query", status.HTTP_400_BAD_REQUEST)
        try:
            return Response(discover_remote_strategy_candidates(payload), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


class StrategyCandidateReviewAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, candidate_id: str):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        payload = {
            "candidate_id": candidate_id,
            "action": str(request.data.get("action") or "").strip(),
            "reviewer": request.data.get("reviewer"),
            "reviewer_note": str(request.data.get("reviewer_note") or ""),
            "edits": request.data.get("edits") if isinstance(request.data.get("edits"), dict) else {},
        }
        if payload["action"] not in {"approve", "reject", "mark_duplicate", "request_changes"}:
            return _error_response("Invalid review action.", "invalid_review_action", status.HTTP_400_BAD_REQUEST)
        try:
            return Response(review_remote_strategy_candidate(payload), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


class StrategyCandidateProcessAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, candidate_id: str):
        if not settings.MCP_ENABLED:
            return _error_response("MCP server is disabled.", "mcp_disabled", status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            limit = int(request.data.get("limit") or 1)
            return Response(process_remote_approved_strategy(candidate_id, limit=limit), status=status.HTTP_200_OK)
        except MCPClientError as exc:
            return _error_response(str(exc), exc.code, status.HTTP_502_BAD_GATEWAY)


def _error_response(message: str, code: str, response_status: int) -> Response:
    return Response({"status": "error", "message": message, "errors": [code]}, status=response_status)
