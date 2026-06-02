from django.urls import path

from apps.analytics.views import AnalyticsStatusAPIView
from apps.agent.views import ChatAPIView
from apps.backtesting.views import BacktestAPIView


urlpatterns = [
    path("api/analytics/status/", AnalyticsStatusAPIView.as_view(), name="analytics-status"),
    path("api/backtest/", BacktestAPIView.as_view(), name="backtest"),
    path("api/chat/", ChatAPIView.as_view(), name="chat"),
]
