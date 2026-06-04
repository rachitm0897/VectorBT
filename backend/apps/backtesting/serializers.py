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


class PortfolioOptimizationRequestSerializer(serializers.Serializer):
    symbols = serializers.ListField(
        child=serializers.CharField(max_length=32),
        max_length=20,
        required=False,
        default=list,
        allow_empty=True,
    )
    sector = serializers.CharField(required=False, allow_blank=True, max_length=80)
    lookback = serializers.ChoiceField(
        choices=["1mo", "6mo", "1y", "2y", "5y"],
        required=False,
        default="2y",
    )
    resolution = serializers.ChoiceField(choices=["D"], required=False, default="D")
    objective = serializers.ChoiceField(
        choices=["max_sharpe", "min_volatility"],
        required=False,
        default="max_sharpe",
    )
    risk_free_rate = serializers.FloatField(required=False, default=0.0, min_value=0.0, max_value=0.25)
    allow_short = serializers.BooleanField(required=False, default=False)
    max_weight = serializers.FloatField(required=False, default=0.6, min_value=0.05, max_value=1.0)
    num_frontier_portfolios = serializers.IntegerField(required=False, default=3000, min_value=100, max_value=10000)

    def validate_symbols(self, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_symbol in value:
            symbol = str(raw_symbol or "").strip().upper()
            if ":" in symbol:
                symbol = symbol.split(":")[-1]
            if not symbol:
                continue
            if symbol not in seen:
                normalized.append(symbol)
                seen.add(symbol)

        return normalized

    def validate(self, attrs):
        symbols = attrs.get("symbols") or []
        sector = str(attrs.get("sector") or "").strip()
        attrs["sector"] = sector

        if symbols and len(symbols) < 2:
            raise serializers.ValidationError({"symbols": "At least two symbols are required."})
        if not symbols and not sector:
            raise serializers.ValidationError("Provide either symbols or a sector for portfolio optimization.")
        return attrs
