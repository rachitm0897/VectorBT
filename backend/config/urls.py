from django.urls import path

from apps.analytics.views import AnalyticsStatusAPIView
from apps.agent.views import ChatAPIView, MCPStatusAPIView
from apps.backtesting.views import BacktestAPIView


urlpatterns = [
    path("api/analytics/status/", AnalyticsStatusAPIView.as_view(), name="analytics-status"),
    path("api/mcp/status/", MCPStatusAPIView.as_view(), name="mcp-status"),
    path("api/backtest/", BacktestAPIView.as_view(), name="backtest"),
    path("api/chat/", ChatAPIView.as_view(), name="chat"),
]
