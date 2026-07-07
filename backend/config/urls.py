from django.http import JsonResponse
from django.urls import include, path

from apps.analytics.views import AnalyticsStatusAPIView
from apps.agent.views import ChatAPIView, ChatStreamAPIView
from apps.backtesting.views import (
    BacktestAPIView,
    FactorPortfolioAPIView,
    MCPStatusAPIView,
    MCPToolInventoryAPIView,
    MultiStockResearchAPIView,
    PortfolioOptimizeAPIView,
    RawAssetMonteCarloAPIView,
    RawMarkowitzResearchAPIView,
    ResearchRunDetailsAPIView,
    ResearchRunsAPIView,
    SingleStockResearchAPIView,
    SystemDiagnosticsAPIView,
    SystemHealthAPIView,
    UniverseResolveSymbolsAPIView,
    UniverseSectorsAPIView,
    UniverseStocksAPIView,
)
from apps.strategies.views import (
    StrategyCandidateProcessAPIView,
    StrategyCandidateReviewAPIView,
    StrategyDetailsAPIView,
    StrategyDiscoveryAPIView,
    StrategyRegistryAPIView,
    StrategyRegistryStatusAPIView,
    StrategyRegistrySyncAPIView,
)


def health_live(_request):
    return JsonResponse({"status": "ok"})


api_patterns = [
    path("health/live/", health_live, name="health-live"),
    path("analytics/status/", AnalyticsStatusAPIView.as_view(), name="analytics-status"),
    path("mcp/status/", MCPStatusAPIView.as_view(), name="mcp-status"),
    path("mcp/tools/", MCPToolInventoryAPIView.as_view(), name="mcp-tools"),
    path("system/health/", SystemHealthAPIView.as_view(), name="system-health"),
    path("system/diagnostics/", SystemDiagnosticsAPIView.as_view(), name="system-diagnostics"),
    path("backtest/", BacktestAPIView.as_view(), name="backtest"),
    path("research/single/", SingleStockResearchAPIView.as_view(), name="research-single"),
    path("research/multi/", MultiStockResearchAPIView.as_view(), name="research-multi"),
    path("research/portfolio/raw/", RawMarkowitzResearchAPIView.as_view(), name="research-portfolio-raw"),
    path("research/monte-carlo/raw/", RawAssetMonteCarloAPIView.as_view(), name="research-monte-carlo-raw"),
    path("research/runs/", ResearchRunsAPIView.as_view(), name="research-runs"),
    path("research/runs/<str:run_id>/", ResearchRunDetailsAPIView.as_view(), name="research-run-details"),
    path("portfolio/optimize/", PortfolioOptimizeAPIView.as_view(), name="portfolio-optimize"),
    path("portfolio/factor/", FactorPortfolioAPIView.as_view(), name="factor-portfolio"),
    path("strategies/", StrategyRegistryAPIView.as_view(), name="strategy-registry"),
    path("strategies/status/", StrategyRegistryStatusAPIView.as_view(), name="strategy-registry-status"),
    path("strategies/sync/", StrategyRegistrySyncAPIView.as_view(), name="strategy-registry-sync"),
    path("strategies/<str:strategy_id>/", StrategyDetailsAPIView.as_view(), name="strategy-details"),
    path("discovery/candidates/", StrategyDiscoveryAPIView.as_view(), name="strategy-discovery"),
    path(
        "discovery/candidates/<str:candidate_id>/review/",
        StrategyCandidateReviewAPIView.as_view(),
        name="strategy-candidate-review",
    ),
    path(
        "discovery/candidates/<str:candidate_id>/process/",
        StrategyCandidateProcessAPIView.as_view(),
        name="strategy-candidate-process",
    ),
    path("universe/sectors/", UniverseSectorsAPIView.as_view(), name="universe-sectors"),
    path("universe/stocks/", UniverseStocksAPIView.as_view(), name="universe-stocks"),
    path("universe/resolve-sector/", UniverseResolveSymbolsAPIView.as_view(), name="universe-resolve-sector"),
    path("chat/", ChatAPIView.as_view(), name="chat"),
    path("chat/stream/", ChatStreamAPIView.as_view(), name="chat-stream"),
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
