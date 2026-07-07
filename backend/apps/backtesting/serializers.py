from rest_framework import serializers

from apps.portfolio_contracts import (
    FACTOR_DEFAULTS,
    FACTOR_GROUPS,
    PORTFOLIO_MONTE_CARLO_DEFAULTS,
    PORTFOLIO_SCENARIOS,
)
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
    initial_cash = serializers.FloatField(required=False, default=10000.0, min_value=1.0)
    fees = serializers.FloatField(required=False, default=0.001, min_value=0.0)
    objective = serializers.ChoiceField(
        choices=["max_sharpe", "min_volatility", "target_return", "target_volatility"],
        required=False,
        default="max_sharpe",
    )
    risk_free_rate = serializers.FloatField(required=False, default=0.0, min_value=0.0, max_value=0.25)
    target_return = serializers.FloatField(required=False, allow_null=True)
    target_volatility = serializers.FloatField(required=False, allow_null=True)
    allow_short = serializers.BooleanField(required=False, default=False)
    min_weight = serializers.FloatField(required=False, allow_null=True, min_value=-1.0, max_value=1.0)
    max_weight = serializers.FloatField(required=False, default=0.6, min_value=0.05, max_value=1.0)
    gross_exposure_limit = serializers.FloatField(required=False, default=1.0, min_value=0.01, max_value=3.0)
    net_exposure = serializers.FloatField(required=False, default=1.0, min_value=-1.0, max_value=1.0)
    covariance_regularization = serializers.FloatField(required=False, default=0.000001, min_value=0.0, max_value=1.0)
    covariance_method = serializers.CharField(required=False, allow_blank=True, max_length=64)
    num_frontier_portfolios = serializers.IntegerField(required=False, default=3000, min_value=100, max_value=10000)
    monte_carlo = serializers.DictField(required=False, default=dict)

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

    def validate_monte_carlo(self, value) -> dict:
        return _normalize_portfolio_monte_carlo(value)

    def validate(self, attrs):
        symbols = attrs.get("symbols") or []
        sector = str(attrs.get("sector") or "").strip()
        attrs["sector"] = sector
        attrs["monte_carlo"] = attrs.get("monte_carlo") or dict(PORTFOLIO_MONTE_CARLO_DEFAULTS)
        if attrs.get("objective") == "target_return" and attrs.get("target_return") is None:
            raise serializers.ValidationError({"target_return": "target_return is required for target_return objective."})
        if attrs.get("objective") == "target_volatility" and attrs.get("target_volatility") is None:
            raise serializers.ValidationError({"target_volatility": "target_volatility is required for target_volatility objective."})

        if symbols and len(symbols) < 2:
            raise serializers.ValidationError({"symbols": "At least two symbols are required."})
        if not symbols and not sector:
            raise serializers.ValidationError("Provide either symbols or a sector for portfolio optimization.")
        return attrs


class FactorPortfolioRequestSerializer(serializers.Serializer):
    symbols = serializers.ListField(
        child=serializers.CharField(max_length=32),
        max_length=50,
        required=False,
        default=list,
        allow_empty=True,
    )
    sector = serializers.CharField(required=False, allow_blank=True, max_length=80)
    selection_mode = serializers.ChoiceField(choices=["symbols", "sector"], required=False, default="symbols")
    lookback = serializers.ChoiceField(choices=["1mo", "6mo", "1y", "2y", "5y"], required=False, default="2y")
    resolution = serializers.ChoiceField(choices=["D"], required=False, default="D")
    factor_model = serializers.DictField(required=False, default=dict)
    optimization = serializers.DictField(required=False, default=dict)
    score_tilt = serializers.DictField(required=False, default=dict)
    monte_carlo = serializers.DictField(required=False, default=dict)

    def validate_symbols(self, value: list[str]) -> list[str]:
        return PortfolioOptimizationRequestSerializer().validate_symbols(value)

    def validate_factor_model(self, value) -> dict:
        return _normalize_factor_model(value if isinstance(value, dict) else {})

    def validate_optimization(self, value) -> dict:
        raw = value if isinstance(value, dict) else {}
        method = str(raw.get("expected_return_method") or "historical").strip().lower()
        if method not in {"historical", "factor_tilted"}:
            raise serializers.ValidationError("invalid_expected_return_method")
        objective = str(raw.get("objective") or "max_sharpe").strip().lower()
        if objective not in {"max_sharpe", "min_volatility"}:
            raise serializers.ValidationError("invalid_objective")
        return {
            "objective": objective,
            "minimum_weight": _float_range(raw.get("minimum_weight"), 0.0, 0.0, 1.0, "invalid_minimum_weight"),
            "maximum_weight": _float_range(raw.get("maximum_weight"), 0.25, 0.05, 1.0, "invalid_maximum_weight"),
            "risk_free_rate": _float_range(raw.get("risk_free_rate"), 0.04, 0.0, 0.25, "invalid_risk_free_rate"),
            "expected_return_method": method,
            "num_frontier_portfolios": _int_range(raw.get("num_frontier_portfolios"), 3000, 100, 10000, "invalid_num_frontier_portfolios"),
        }

    def validate_score_tilt(self, value) -> dict:
        raw = value if isinstance(value, dict) else {}
        return {
            "enabled": bool(raw.get("enabled", False)),
            "strength": _float_range(raw.get("strength"), 0.20, 0.0, 1.0, "invalid_score_tilt_strength"),
            "maximum_adjustment_pct": _float_range(raw.get("maximum_adjustment_pct"), 0.05, 0.0, 0.50, "invalid_score_tilt_cap"),
        }

    def validate_monte_carlo(self, value) -> dict:
        return _normalize_portfolio_monte_carlo(value)

    def validate(self, attrs):
        symbols = attrs.get("symbols") or []
        sector = str(attrs.get("sector") or "").strip()
        attrs["sector"] = sector
        if attrs.get("selection_mode") == "sector" and not sector:
            raise serializers.ValidationError({"sector": "Sector is required for sector selection."})
        if attrs.get("selection_mode") != "sector" and len(symbols) < 2:
            raise serializers.ValidationError({"symbols": "At least two symbols are required."})
        return attrs


class SingleStockResearchRequestSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=64)
    strategy_id = serializers.CharField(max_length=128)
    parameters = serializers.DictField(required=False, default=dict)
    lookback = serializers.ChoiceField(choices=["1mo", "6mo", "1y", "2y", "5y"], required=False, default="2y")
    resolution = serializers.ChoiceField(choices=["D"], required=False, default="D")
    initial_cash = serializers.FloatField(required=False, default=10000.0, min_value=1.0)
    fees = serializers.FloatField(required=False, default=0.001, min_value=0.0)
    monte_carlo = serializers.DictField(required=False, default=dict)

    def validate_symbol(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("symbol is required.")
        return value

    def validate_monte_carlo(self, value) -> dict:
        return _normalize_research_monte_carlo(value, mode="strategy_returns")


class MultiStockResearchRequestSerializer(serializers.Serializer):
    symbols = serializers.ListField(
        child=serializers.CharField(max_length=32),
        min_length=2,
        max_length=30,
    )
    strategy_id = serializers.CharField(max_length=128)
    parameters = serializers.DictField(required=False, default=dict)
    lookback = serializers.ChoiceField(choices=["1mo", "6mo", "1y", "2y", "5y"], required=False, default="2y")
    resolution = serializers.ChoiceField(choices=["D"], required=False, default="D")
    initial_cash = serializers.FloatField(required=False, default=10000.0, min_value=1.0)
    fees = serializers.FloatField(required=False, default=0.001, min_value=0.0)
    optimization = serializers.DictField(required=False, default=dict)
    monte_carlo = serializers.DictField(required=False, default=dict)

    def validate_symbols(self, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_symbol in value:
            symbol = str(raw_symbol or "").strip().upper()
            if ":" in symbol:
                symbol = symbol.split(":")[-1]
            if symbol and symbol not in seen:
                normalized.append(symbol)
                seen.add(symbol)
        if len(normalized) < 2:
            raise serializers.ValidationError("At least two unique symbols are required.")
        return normalized

    def validate_monte_carlo(self, value) -> dict:
        return _normalize_research_monte_carlo(value, mode="portfolio_returns")


class RawMonteCarloRequestSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=64)
    lookback = serializers.ChoiceField(choices=["1mo", "6mo", "1y", "2y", "5y"], required=False, default="2y")
    resolution = serializers.ChoiceField(choices=["D"], required=False, default="D")
    start_value = serializers.FloatField(required=False, default=10000.0, min_value=1.0)
    days = serializers.IntegerField(required=False, default=60, min_value=1, max_value=252)
    simulations = serializers.IntegerField(required=False, default=500, min_value=10, max_value=5000)
    method = serializers.ChoiceField(choices=["bootstrap", "block_bootstrap"], required=False, default="bootstrap")
    seed = serializers.IntegerField(required=False, allow_null=True, default=42)

    def validate_symbol(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("symbol is required.")
        return value


def _normalize_portfolio_monte_carlo(value) -> dict:
    raw = value if isinstance(value, dict) else {}
    config = {
        **PORTFOLIO_MONTE_CARLO_DEFAULTS,
        "scenarios": list(PORTFOLIO_SCENARIOS),
        "scenario_overrides": {},
    }
    config.update({key: item for key, item in raw.items() if item is not None})
    if "horizon_days" in raw and "days" not in raw:
        config["days"] = raw["horizon_days"]
    if "simulation_count" in raw and "simulations" not in raw:
        config["simulations"] = raw["simulation_count"]

    config["enabled"] = bool(config.get("enabled", False))
    config["days"] = _validated_int(config.get("days"), 1, 252, "invalid_monte_carlo_days")
    config["simulations"] = _validated_int(
        config.get("simulations"),
        100,
        5000,
        "invalid_monte_carlo_simulations",
    )
    config["block_size"] = _validated_int(config.get("block_size"), 1, 20, "invalid_block_size")
    config["seed"] = _validated_seed(config.get("seed"))
    config["scenarios"] = _validated_scenarios(config.get("scenarios"))
    config["scenario_overrides"] = _validated_scenario_overrides(config.get("scenario_overrides"))
    return config


def _normalize_research_monte_carlo(value, *, mode: str) -> dict:
    raw = value if isinstance(value, dict) else {}
    days = raw.get("days", raw.get("horizon_days", raw.get("horizon", 60)))
    simulations = raw.get("simulations", raw.get("simulation_count", 500))
    thresholds = raw.get("thresholds", raw.get("loss_thresholds", [-0.10, -0.20]))
    if not isinstance(thresholds, list):
        raise serializers.ValidationError("invalid_monte_carlo_thresholds")
    return {
        "enabled": bool(raw.get("enabled", True)),
        "method": str(raw.get("method") or "bootstrap"),
        "mode": mode,
        "days": _validated_int(days, 1, 252, "invalid_monte_carlo_days"),
        "simulations": _validated_int(simulations, 10, 5000, "invalid_monte_carlo_simulations"),
        "block_size": _validated_int(raw.get("block_size", 5), 1, 20, "invalid_block_size"),
        "seed": _validated_seed(raw.get("seed", 42)),
        "thresholds": [_float_value(item, -0.1) for item in thresholds],
    }


def _validated_int(value, minimum: int, maximum: int, code: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError(code)
    if parsed < minimum or parsed > maximum:
        raise serializers.ValidationError(code)
    return parsed


def _validated_seed(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError("invalid_monte_carlo_seed")


def _validated_scenarios(value) -> list[str]:
    if value is None:
        return list(PORTFOLIO_SCENARIOS)
    if not isinstance(value, list) or not value:
        raise serializers.ValidationError("invalid_scenario")
    scenarios = [str(item or "").strip().lower() for item in value]
    if any(item not in PORTFOLIO_SCENARIOS for item in scenarios):
        raise serializers.ValidationError("invalid_scenario")
    return scenarios


def _validated_scenario_overrides(value) -> dict:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise serializers.ValidationError("invalid_scenario_override")

    allowed_fields = {"drift_shift_annual", "volatility_multiplier", "initial_shock_pct"}
    overrides: dict[str, dict[str, float]] = {}
    for raw_name, raw_override in value.items():
        name = str(raw_name or "").strip().lower()
        if name not in PORTFOLIO_SCENARIOS or not isinstance(raw_override, dict):
            raise serializers.ValidationError("invalid_scenario_override")
        if set(raw_override) - allowed_fields:
            raise serializers.ValidationError("invalid_scenario_override")

        cleaned: dict[str, float] = {}
        for field, raw_field_value in raw_override.items():
            if raw_field_value is None or raw_field_value == "":
                continue
            try:
                parsed = float(raw_field_value)
            except (TypeError, ValueError):
                raise serializers.ValidationError("invalid_scenario_override")
            if field == "drift_shift_annual" and not -0.50 <= parsed <= 0.50:
                raise serializers.ValidationError("invalid_scenario_override")
            if field == "volatility_multiplier" and not 0.25 <= parsed <= 4.0:
                raise serializers.ValidationError("invalid_scenario_override")
            if field == "initial_shock_pct" and not -0.80 <= parsed <= 0.80:
                raise serializers.ValidationError("invalid_scenario_override")
            cleaned[field] = parsed
        if cleaned:
            overrides[name] = cleaned
    return overrides


def _normalize_factor_model(raw: dict) -> dict:
    config = {**FACTOR_DEFAULTS, "weights": dict(FACTOR_DEFAULTS["weights"])}
    config.update({key: value for key, value in raw.items() if value is not None})
    mode = str(config.get("normalization_mode") or "sector").strip().lower()
    if mode not in {"universe", "sector"}:
        raise serializers.ValidationError("invalid_normalization_mode")
    method = str(config.get("selection_method") or "top_n").strip().lower()
    if method not in {"top_n", "top_percentile", "minimum_score", "all_eligible"}:
        raise serializers.ValidationError("invalid_selection_method")
    weights = config.get("weights") if isinstance(config.get("weights"), dict) else {}
    parsed_weights = {group: _float_value(weights.get(group), FACTOR_DEFAULTS["weights"][group]) for group in FACTOR_GROUPS}
    if any(value < 0 for value in parsed_weights.values()) or abs(sum(parsed_weights.values()) - 1.0) > 1e-6:
        raise serializers.ValidationError("invalid_factor_weights")
    return {
        "enabled": bool(config.get("enabled", True)),
        "normalization_mode": mode,
        "weights": parsed_weights,
        "minimum_data_coverage_pct": _float_range(config.get("minimum_data_coverage_pct"), 60.0, 0.0, 100.0, "invalid_minimum_data_coverage"),
        "selection_method": method,
        "top_n": _int_range(config.get("top_n"), 10, 1, 50, "invalid_top_n"),
        "top_percentile": _float_range(config.get("top_percentile"), 30.0, 1.0, 100.0, "invalid_top_percentile"),
        "minimum_score": None if config.get("minimum_score") in (None, "") else _float_range(config.get("minimum_score"), 65.0, 0.0, 100.0, "invalid_minimum_score"),
    }


def _float_value(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _float_range(value, default: float, minimum: float, maximum: float, code: str) -> float:
    parsed = _float_value(value, default)
    if parsed < minimum or parsed > maximum:
        raise serializers.ValidationError(code)
    return parsed


def _int_range(value, default: int, minimum: int, maximum: int, code: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < minimum or parsed > maximum:
        raise serializers.ValidationError(code)
    return parsed
