PORTFOLIO_SCENARIOS = ("neutral", "bullish", "bearish", "crash")

PORTFOLIO_MONTE_CARLO_DEFAULTS = {
    "enabled": False,
    "days": 60,
    "simulations": 500,
    "block_size": 5,
    "seed": 42,
    "scenarios": list(PORTFOLIO_SCENARIOS),
    "scenario_overrides": {},
}

PORTFOLIO_DEFAULTS = {
    "lookback": "2y",
    "resolution": "D",
    "objective": "max_sharpe",
    "risk_free_rate": 0.0,
    "allow_short": False,
    "max_weight": 0.6,
    "num_frontier_portfolios": 3000,
    "monte_carlo": PORTFOLIO_MONTE_CARLO_DEFAULTS,
}

FACTOR_GROUPS = ("fundamental_quality", "valuation", "momentum", "analyst", "financial_risk")

FACTOR_DEFAULTS = {
    "enabled": True,
    "normalization_mode": "sector",
    "weights": {
        "fundamental_quality": 0.30,
        "valuation": 0.20,
        "momentum": 0.20,
        "analyst": 0.15,
        "financial_risk": 0.15,
    },
    "minimum_data_coverage_pct": 60.0,
    "selection_method": "top_n",
    "top_n": 10,
    "top_percentile": 30.0,
    "minimum_score": None,
}

FACTOR_PORTFOLIO_DEFAULTS = {
    "selection_mode": "symbols",
    "lookback": "2y",
    "resolution": "D",
    "factor_model": FACTOR_DEFAULTS,
    "optimization": {
        "objective": "max_sharpe",
        "minimum_weight": 0,
        "maximum_weight": 0.25,
        "risk_free_rate": 0.04,
        "expected_return_method": "historical",
    },
    "score_tilt": {
        "enabled": False,
        "strength": 0.20,
        "maximum_adjustment_pct": 0.05,
    },
    "monte_carlo": {
        **PORTFOLIO_MONTE_CARLO_DEFAULTS,
        "enabled": True,
    },
}
