from django.http import JsonResponse
from django.urls import include, path

from apps.analytics.views import AnalyticsStatusAPIView
from apps.agent.views import ChatAPIView
from apps.backtesting.views import (
    BacktestAPIView,
    FactorPortfolioAPIView,
    MCPStatusAPIView,
    PortfolioOptimizeAPIView,
    UniverseSectorsAPIView,
    UniverseStocksAPIView,
)


def health_live(_request):
    return JsonResponse({"status": "ok"})


api_patterns = [
    path("health/live/", health_live, name="health-live"),
    path("analytics/status/", AnalyticsStatusAPIView.as_view(), name="analytics-status"),
    path("mcp/status/", MCPStatusAPIView.as_view(), name="mcp-status"),
    path("backtest/", BacktestAPIView.as_view(), name="backtest"),
    path("portfolio/optimize/", PortfolioOptimizeAPIView.as_view(), name="portfolio-optimize"),
    path("portfolio/factor/", FactorPortfolioAPIView.as_view(), name="factor-portfolio"),
    path("universe/sectors/", UniverseSectorsAPIView.as_view(), name="universe-sectors"),
    path("universe/stocks/", UniverseStocksAPIView.as_view(), name="universe-stocks"),
    path("chat/", ChatAPIView.as_view(), name="chat"),
]

urlpatterns = [
    path("mcp/status/", MCPStatusAPIView.as_view(), name="mcp-status-root"),
    path("insta_backtester/mcp/status/", MCPStatusAPIView.as_view(), name="mcp-status-prefixed"),
    path("api/", include(api_patterns)),
    path("insta_backtester/api/", include(api_patterns)),
    path("insta_backtester/v1/", include(api_patterns)),
    path("insta_backtester_api/v1/", include(api_patterns)),
    path("vectorbt_api/v1/", include(api_patterns)),
    path("v1/", include(api_patterns)),
]
