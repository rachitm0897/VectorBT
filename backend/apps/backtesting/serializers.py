from rest_framework import serializers

from apps.strategies.registry import SUPPORTED_STRATEGIES


class MonteCarloSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(default=False)
    days = serializers.IntegerField(default=60, min_value=1, max_value=365)
    simulations = serializers.IntegerField(default=500, min_value=1, max_value=5000)
    method = serializers.ChoiceField(choices=["bootstrap"], default="bootstrap")


class BacktestRequestSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=64)
    strategy = serializers.ChoiceField(choices=sorted(SUPPORTED_STRATEGIES))
    parameters = serializers.DictField(required=False, default=dict)
    lookback = serializers.RegexField(regex=r"^\d+[dmy]$", required=False, default="2y")
    resolution = serializers.ChoiceField(choices=["D"], required=False, default="D")
    initial_cash = serializers.FloatField(required=False, default=10000.0, min_value=1.0)
    fees = serializers.FloatField(required=False, default=0.0, min_value=0.0)
    monte_carlo = MonteCarloSerializer(required=False, default=dict)

    def validate_symbol(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("symbol is required.")
        return value
