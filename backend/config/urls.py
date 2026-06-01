from django.urls import path

from apps.backtesting.views import BacktestAPIView


urlpatterns = [
    path("api/backtest/", BacktestAPIView.as_view(), name="backtest"),
]
