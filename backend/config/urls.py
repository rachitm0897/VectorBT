from django.urls import path

from apps.agent.views import ChatAPIView
from apps.backtesting.views import BacktestAPIView


urlpatterns = [
    path("api/backtest/", BacktestAPIView.as_view(), name="backtest"),
    path("api/chat/", ChatAPIView.as_view(), name="chat"),
]
