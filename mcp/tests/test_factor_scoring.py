import math

import pandas as pd

import tools.factor_scoring as factors


def scored_records():
    return [
        {
            "ticker": "AAA",
            "company_name": "AAA Corp",
            "sector": "Technology",
            "raw_factor_values": {
                "return_on_equity": 0.30,
                "return_on_assets": 0.14,
                "operating_margin": 0.25,
                "net_profit_margin": 0.20,
                "revenue_growth": 0.12,
                "earnings_growth": 0.15,
                "free_cash_flow_margin": 0.18,
                "debt_to_equity": 0.20,
                "interest_coverage": 15,
                "current_ratio": 2.5,
                "earnings_consistency": 1.0,
                "price_to_earnings": 18,
                "price_to_book": 4,
                "price_to_sales": 6,
                "enterprise_value_to_ebitda": 14,
                "free_cash_flow_yield": 0.04,
                "return_1m": 0.04,
                "return_3m": 0.12,
                "return_6m": 0.22,
                "distance_50d_ma": 0.05,
                "historical_volatility": 0.18,
                "maximum_drawdown": 0.10,
                "downside_volatility": 0.11,
                "financial_distress_proxy": 0.16,
            },
        },
        {
            "ticker": "BBB",
            "company_name": "BBB Corp",
            "sector": "Technology",
            "raw_factor_values": {
                "return_on_equity": 0.08,
                "return_on_assets": 0.03,
                "operating_margin": 0.08,
                "net_profit_margin": 0.04,
                "revenue_growth": 0.02,
                "earnings_growth": 0.01,
                "free_cash_flow_margin": 0.03,
                "debt_to_equity": 1.8,
                "interest_coverage": 2,
                "current_ratio": 0.9,
                "earnings_consistency": 0.25,
                "price_to_earnings": 40,
                "price_to_book": 12,
                "price_to_sales": 16,
                "enterprise_value_to_ebitda": 30,
                "free_cash_flow_yield": 0.01,
                "return_1m": -0.03,
                "return_3m": -0.08,
                "return_6m": -0.12,
                "distance_50d_ma": -0.06,
                "historical_volatility": 0.45,
                "maximum_drawdown": 0.35,
                "downside_volatility": 0.30,
                "financial_distress_proxy": 0.80,
            },
        },
        {
            "ticker": "CCC",
            "company_name": "CCC Corp",
            "sector": "Healthcare",
            "raw_factor_values": {
                "return_on_equity": 0.18,
                "return_on_assets": 0.08,
                "operating_margin": 0.15,
                "net_profit_margin": 0.12,
                "price_to_earnings": 12,
                "price_to_book": 2,
                "price_to_sales": 3,
                "historical_volatility": 0.22,
                "maximum_drawdown": 0.16,
                "downside_volatility": 0.14,
            },
        },
    ]


def test_higher_profitability_receives_better_quality_rank():
    result = {item["ticker"]: item for item in factors.calculate_factor_scores(scored_records())}

    assert result["AAA"]["fundamental_quality_score"] > result["BBB"]["fundamental_quality_score"]


def test_lower_valuation_multiples_receive_better_valuation_rank():
    result = {item["ticker"]: item for item in factors.calculate_factor_scores(scored_records())}

    assert result["CCC"]["valuation_score"] > result["BBB"]["valuation_score"]


def test_lower_risk_receives_better_financial_risk_score():
    result = {item["ticker"]: item for item in factors.calculate_factor_scores(scored_records())}

    assert result["AAA"]["financial_risk_score"] > result["BBB"]["financial_risk_score"]


def test_missing_data_does_not_automatically_produce_zero():
    result = {item["ticker"]: item for item in factors.calculate_factor_scores(scored_records())}

    assert result["CCC"]["analyst_score"] is None
    assert result["CCC"]["combined_portfolio_score"] > 0


def test_effective_weights_are_redistributed_when_group_missing():
    result = {item["ticker"]: item for item in factors.calculate_factor_scores(scored_records())}

    weights = result["CCC"]["effective_factor_weights"]
    assert "analyst" not in weights
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9)


def test_scores_remain_between_zero_and_one_hundred():
    result = factors.calculate_factor_scores(scored_records())

    for item in result:
        for key in (
            "fundamental_quality_score",
            "valuation_score",
            "momentum_score",
            "financial_risk_score",
            "combined_portfolio_score",
        ):
            value = item[key]
            if value is not None:
                assert 0 <= value <= 100


def test_factor_weights_are_validated():
    try:
        factors.validate_factor_weights({"fundamental_quality": 1.0})
    except ValueError as exc:
        assert "sum" in str(exc)
    else:
        raise AssertionError("Invalid weights should fail validation.")


def test_selection_methods_return_expected_stocks():
    result = factors.calculate_factor_scores(scored_records())

    selected, rejected = factors.select_factor_stocks(result, method="top_n", top_n=1, minimum_data_coverage_pct=0)

    assert len(selected) == 1
    assert rejected
    assert selected[0]["selection_status"] == "selected"


def test_factor_return_tilt_respects_maximum_cap():
    selected = [
        {"ticker": "AAA", "combined_portfolio_score": 100},
        {"ticker": "BBB", "combined_portfolio_score": 0},
    ]

    adjusted = factors.apply_factor_return_tilt(
        {"AAA": 0.10, "BBB": 0.10},
        selected,
        strength=1.0,
        maximum_adjustment_pct=0.05,
    )

    assert math.isclose(adjusted["AAA"], 0.15, abs_tol=1e-12)
    assert math.isclose(adjusted["BBB"], 0.05, abs_tol=1e-12)


def test_construct_factor_portfolio_uses_markowitz_and_scenarios(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    dates = pd.date_range("2024-01-01", periods=280, freq="D", tz="UTC")
    prices = pd.DataFrame(
        {
            "AAPL": [100 + index * 0.2 for index in range(len(dates))],
            "MSFT": [90 + index * 0.15 for index in range(len(dates))],
            "NVDA": [80 + index * 0.3 for index in range(len(dates))],
        },
        index=dates,
    )
    monkeypatch.setattr(factors, "fetch_multi_symbol_close_prices", lambda symbols, **_kwargs: prices[symbols])
    monkeypatch.setattr(
        factors,
        "fetch_finnhub_factor_data",
        lambda symbol, api_key=None: {
            "profile": {"name": symbol, "finnhubIndustry": "Technology"},
            "metrics": {"metric": {"roeTTM": 0.2, "peTTM": 20, "beta": 1.0}},
            "recommendations": [],
            "earnings": [],
            "warnings": [],
        },
    )

    result = factors.construct_factor_portfolio_core(
        symbols=["AAPL", "MSFT", "NVDA"],
        factor_model={"minimum_data_coverage_pct": 0, "top_n": 2},
        optimization={"maximum_weight": 0.6},
        monte_carlo={"enabled": True, "days": 5, "simulations": 100, "block_size": 2, "scenarios": ["neutral"]},
    )

    assert result["status"] == "success"
    assert result["selected_stocks"]
    assert result["optimization_result"]["weights"]
    assert result["scenario_analysis"]["enabled"] is True
