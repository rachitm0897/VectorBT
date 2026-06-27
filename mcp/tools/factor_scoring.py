from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from tools.market_data import fetch_finnhub_factor_data
from tools.portfolio_optimization import fetch_multi_symbol_close_prices, run_markowitz_optimization_core
from tools.universe import get_stock_by_ticker, resolve_symbols_for_sector, validate_symbols


TRADING_DAYS = 252
GROUPS = (
    "fundamental_quality",
    "valuation",
    "momentum",
    "analyst",
    "financial_risk",
)
DEFAULT_FACTOR_WEIGHTS = {
    "fundamental_quality": 0.30,
    "valuation": 0.20,
    "momentum": 0.20,
    "analyst": 0.15,
    "financial_risk": 0.15,
}
FACTOR_DEFINITIONS: dict[str, dict[str, bool]] = {
    "fundamental_quality": {
        "return_on_equity": True,
        "return_on_assets": True,
        "operating_margin": True,
        "net_profit_margin": True,
        "revenue_growth": True,
        "earnings_growth": True,
        "free_cash_flow_margin": True,
        "debt_to_equity": False,
        "interest_coverage": True,
        "current_ratio": True,
        "earnings_consistency": True,
    },
    "valuation": {
        "price_to_earnings": False,
        "forward_price_to_earnings": False,
        "price_to_book": False,
        "price_to_sales": False,
        "enterprise_value_to_ebitda": False,
        "free_cash_flow_yield": True,
    },
    "momentum": {
        "return_1m": True,
        "return_3m": True,
        "return_6m": True,
        "return_12m": True,
        "return_excluding_latest_month": True,
        "distance_50d_ma": True,
        "distance_200d_ma": True,
        "relative_strength": True,
    },
    "analyst": {
        "analyst_recommendation_score": True,
        "earnings_estimate_revision": True,
        "target_price_upside": True,
        "earnings_surprise": True,
        "expected_earnings_change": True,
    },
    "financial_risk": {
        "historical_volatility": False,
        "maximum_drawdown": False,
        "downside_volatility": False,
        "beta": False,
        "debt_to_equity": False,
        "earnings_variability": False,
        "financial_distress_proxy": False,
    },
}


def construct_factor_portfolio_core(
    symbols: list[str] | None = None,
    sector: str | None = None,
    selection_mode: str = "symbols",
    lookback: str = "2y",
    resolution: str = "D",
    factor_model: dict[str, Any] | None = None,
    optimization: dict[str, Any] | None = None,
    score_tilt: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    request_symbols, resolved_sector, universe_warnings = _resolve_universe(
        symbols or [],
        sector,
        selection_mode,
    )
    factor_config = validate_factor_model(factor_model or {})
    optimization_config = validate_optimization_config(optimization or {})
    tilt_config = validate_score_tilt(score_tilt or {})
    monte_carlo_config = validate_monte_carlo_config(monte_carlo or {})

    warnings = list(universe_warnings)
    rejected: list[dict[str, Any]] = []
    if len(request_symbols) < 2:
        return _error("At least two valid symbols are required.", ["insufficient_universe"])

    price_df, price_rejections = _fetch_price_frame(request_symbols, lookback, resolution, finnhub_api_key)
    rejected.extend(price_rejections)
    price_symbols = list(price_df.columns)
    if len(price_symbols) < 2:
        return _error("At least two stocks with usable price history are required.", ["insufficient_price_history"])

    records: list[dict[str, Any]] = []
    for symbol in price_symbols:
        records.append(
            build_factor_record(
                symbol,
                price_df[symbol],
                finnhub_api_key=finnhub_api_key,
            )
        )
    _add_relative_strength(records)

    scored = calculate_factor_scores(
        records,
        requested_weights=factor_config["weights"],
        normalization_mode=factor_config["normalization_mode"],
    )
    selected, selection_rejections = select_factor_stocks(
        scored,
        method=factor_config["selection_method"],
        minimum_data_coverage_pct=factor_config["minimum_data_coverage_pct"],
        top_n=factor_config.get("top_n"),
        top_percentile=factor_config.get("top_percentile"),
        minimum_score=factor_config.get("minimum_score"),
    )
    rejected.extend(selection_rejections)
    selected_symbols = [item["ticker"] for item in selected]
    if len(selected_symbols) < 2:
        return _error(
            "Factor selection returned fewer than two eligible stocks.",
            ["insufficient_selected_stocks"],
            rejected=rejected,
            factor_scores=scored,
        )
    if len(selected_symbols) * optimization_config["maximum_weight"] < 1.0 - 1e-9:
        feasible_weight = 1.0 / len(selected_symbols)
        warnings.append(
            "maximum_weight was raised to the minimum feasible value for the selected stock count."
        )
        optimization_config["maximum_weight"] = feasible_weight

    expected_returns_original = _historical_expected_returns(price_df[selected_symbols])
    expected_returns_adjusted: dict[str, float] | None = None
    expected_return_override = None
    if optimization_config["expected_return_method"] == "factor_tilted":
        expected_returns_adjusted = apply_factor_return_tilt(
            expected_returns_original,
            selected,
            strength=tilt_config["strength"] if tilt_config["enabled"] else 0.20,
            maximum_adjustment_pct=tilt_config["maximum_adjustment_pct"],
        )
        expected_return_override = expected_returns_adjusted

    optimization_result = run_markowitz_optimization_core(
        symbols=selected_symbols,
        sector=None,
        lookback=lookback,
        resolution=resolution,
        objective=optimization_config["objective"],
        risk_free_rate=optimization_config["risk_free_rate"],
        allow_short=False,
        max_weight=optimization_config["maximum_weight"],
        num_frontier_portfolios=optimization_config["num_frontier_portfolios"],
        run_monte_carlo=monte_carlo_config["enabled"],
        monte_carlo_days=monte_carlo_config["days"],
        monte_carlo_simulations=monte_carlo_config["simulations"],
        monte_carlo_block_size=monte_carlo_config["block_size"],
        monte_carlo_seed=monte_carlo_config["seed"],
        monte_carlo_scenarios=monte_carlo_config["scenarios"],
        scenario_overrides=monte_carlo_config["scenario_overrides"],
        finnhub_api_key=finnhub_api_key,
        price_df=price_df[selected_symbols],
        expected_returns_annual=expected_return_override,
    )
    if optimization_result.get("status") != "success":
        return optimization_result

    final_weights = optimization_result.get("weights") if isinstance(optimization_result.get("weights"), dict) else {}
    for item in scored:
        ticker = item["ticker"]
        item["expected_return_original"] = _round(expected_returns_original.get(ticker))
        item["expected_return_adjusted"] = _round(
            (expected_returns_adjusted or expected_returns_original).get(ticker)
        )
        item["final_portfolio_weight"] = _round(float(final_weights.get(ticker, 0.0)), 6)

    selected_lookup = set(selected_symbols)
    for item in scored:
        if item["ticker"] in selected_lookup:
            item["selection_status"] = "selected"
            item["selection_reason"] = "Selected for Markowitz optimization."

    run_id = f"factor_{optimization_result.get('artifact_id', '') or started.strftime('%Y%m%d%H%M%S')}"
    artifact = {
        "request_summary": {
            "symbols": request_symbols,
            "sector": resolved_sector,
            "selection_mode": "sector" if resolved_sector else "symbols",
            "lookback": lookback,
            "resolution": resolution,
        },
        "universe_summary": {
            "symbols_requested": len(request_symbols),
            "symbols_scored": len(scored),
            "symbols_selected": len(selected_symbols),
        },
        "factor_model_configuration": factor_config,
        "factor_scores": scored,
        "selected_stocks": [item for item in scored if item["ticker"] in selected_lookup],
        "rejected_stocks": rejected,
        "optimization_result": optimization_result,
        "portfolio_weights": final_weights,
        "scenario_analysis": optimization_result.get("scenario_analysis"),
        "warnings": warnings,
        "data_sources": {
            "prices": "Finnhub daily candles",
            "fundamentals": "Finnhub company profile, basic financials, recommendations, earnings when available",
        },
        "calculation_timestamp": started.isoformat(),
    }
    from tools.formatting import save_artifact_json
    from tools.portfolio_optimization import _artifact_fields

    artifact_path = save_artifact_json(run_id, artifact)
    artifact_fields = _artifact_fields(artifact_path)
    compact_scores = _compact_scores(scored)
    return {
        "status": "success",
        "tool": "construct_factor_portfolio",
        "run_id": run_id,
        "request_summary": artifact["request_summary"],
        "universe_summary": artifact["universe_summary"],
        "factor_model_configuration": factor_config,
        "factor_scores": compact_scores,
        "selected_stocks": [item for item in compact_scores if item["selection_status"] == "selected"],
        "rejected_stocks": rejected[:200],
        "optimization_result": _compact_optimization_result(optimization_result),
        "portfolio_weights": final_weights,
        "scenario_analysis": optimization_result.get("scenario_analysis"),
        "warnings": warnings,
        "data_sources": artifact["data_sources"],
        "calculation_timestamp": artifact["calculation_timestamp"],
        **artifact_fields,
    }


def build_factor_record(
    symbol: str,
    close_prices: pd.Series,
    finnhub_api_key: str | None = None,
    provider_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stock = get_stock_by_ticker(symbol) or {}
    provider = provider_data if provider_data is not None else fetch_finnhub_factor_data(symbol, api_key=finnhub_api_key)
    metrics = provider.get("metrics") if isinstance(provider.get("metrics"), dict) else {}
    metric_values = metrics.get("metric") if isinstance(metrics.get("metric"), dict) else metrics
    profile = provider.get("profile") if isinstance(provider.get("profile"), dict) else {}
    recommendations = provider.get("recommendations") if isinstance(provider.get("recommendations"), list) else []
    earnings = provider.get("earnings") if isinstance(provider.get("earnings"), list) else []
    raw = {
        **_fundamental_values(metric_values, earnings),
        **_valuation_values(metric_values),
        **_price_values(close_prices, metric_values),
        **_analyst_values(metric_values, recommendations, earnings),
    }
    raw.update(_risk_values(close_prices, metric_values, raw))
    return {
        "ticker": symbol,
        "company_name": profile.get("name") or stock.get("name") or symbol,
        "sector": profile.get("finnhubIndustry") or stock.get("sector") or "Unclassified",
        "raw_factor_values": raw,
        "provider_warnings": provider.get("warnings") if isinstance(provider.get("warnings"), list) else [],
    }


def calculate_factor_scores(
    records: list[dict[str, Any]],
    requested_weights: dict[str, float] | None = None,
    normalization_mode: str = "universe",
    sector_min_count: int = 3,
) -> list[dict[str, Any]]:
    weights = validate_factor_weights(requested_weights or DEFAULT_FACTOR_WEIGHTS)
    scored = [{**record, "normalized_factor_scores": {}} for record in records]
    for group, factors in FACTOR_DEFINITIONS.items():
        for factor, higher_is_better in factors.items():
            _score_factor(
                scored,
                factor,
                higher_is_better=higher_is_better,
                normalization_mode=normalization_mode if group in {"fundamental_quality", "valuation"} else "universe",
                sector_min_count=sector_min_count,
            )

    all_factors = {factor for factors in FACTOR_DEFINITIONS.values() for factor in factors}
    for item in scored:
        normalized = item["normalized_factor_scores"]
        group_scores: dict[str, float | None] = {}
        available_groups: dict[str, float] = {}
        available_factor_count = 0
        for group, factors in FACTOR_DEFINITIONS.items():
            values = [normalized.get(factor) for factor in factors]
            usable = [float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(float(value))]
            if usable:
                group_score = float(np.mean(usable))
                group_scores[group] = _round(group_score)
                available_groups[group] = group_score
                available_factor_count += len(usable)
            else:
                group_scores[group] = None

        effective_weights = _effective_weights(weights, available_groups)
        combined = sum(available_groups[group] * weight for group, weight in effective_weights.items()) if available_groups else 50.0
        quantitative_alpha = _weighted_subset(
            available_groups,
            effective_weights,
            {"valuation", "momentum", "analyst", "financial_risk"},
        )
        item.update(
            {
                "fundamental_quality_score": group_scores["fundamental_quality"],
                "valuation_score": group_scores["valuation"],
                "momentum_score": group_scores["momentum"],
                "analyst_score": group_scores["analyst"],
                "financial_risk_score": group_scores["financial_risk"],
                "quantitative_alpha_score": _round(quantitative_alpha if quantitative_alpha is not None else combined),
                "combined_portfolio_score": _round(combined),
                "data_coverage_pct": _round((available_factor_count / len(all_factors)) * 100.0, 2),
                "requested_factor_weights": dict(weights),
                "effective_factor_weights": effective_weights,
                "selection_status": "unselected",
                "selection_reason": "Awaiting selection.",
                "expected_return_original": None,
                "expected_return_adjusted": None,
                "final_portfolio_weight": 0.0,
            }
        )
    return sorted(scored, key=lambda item: item["combined_portfolio_score"], reverse=True)


def select_factor_stocks(
    scored: list[dict[str, Any]],
    method: str = "top_n",
    minimum_data_coverage_pct: float = 60.0,
    top_n: int | None = 10,
    top_percentile: float | None = None,
    minimum_score: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = []
    rejected = []
    for item in scored:
        if float(item.get("data_coverage_pct") or 0.0) < minimum_data_coverage_pct:
            item["selection_status"] = "rejected"
            item["selection_reason"] = "Insufficient data coverage."
            rejected.append(_rejection(item, "Insufficient data coverage"))
        else:
            eligible.append(item)

    selected: list[dict[str, Any]]
    if method == "top_n":
        selected = eligible[: max(1, int(top_n or 10))]
        threshold = {item["ticker"] for item in selected}
        for item in eligible:
            if item["ticker"] not in threshold:
                item["selection_status"] = "rejected"
                item["selection_reason"] = "Outside selected top N."
                rejected.append(_rejection(item, "Outside selected top N"))
    elif method == "top_percentile":
        percentile = max(1.0, min(float(top_percentile or 30.0), 100.0))
        count = max(1, int(math.ceil(len(eligible) * percentile / 100.0)))
        selected = eligible[:count]
        threshold = {item["ticker"] for item in selected}
        for item in eligible:
            if item["ticker"] not in threshold:
                item["selection_status"] = "rejected"
                item["selection_reason"] = "Outside selected percentile."
                rejected.append(_rejection(item, "Outside selected percentile"))
    elif method == "minimum_score":
        score = float(minimum_score if minimum_score is not None else 65.0)
        selected = [item for item in eligible if float(item["combined_portfolio_score"]) >= score]
        for item in eligible:
            if item not in selected:
                item["selection_status"] = "rejected"
                item["selection_reason"] = "Score below threshold."
                rejected.append(_rejection(item, "Score below threshold"))
    elif method == "all_eligible":
        selected = list(eligible)
    else:
        raise ValueError("selection_method must be top_n, top_percentile, minimum_score, or all_eligible.")

    for item in selected:
        item["selection_status"] = "selected"
        item["selection_reason"] = "Selected by factor model."
    return selected, rejected


def validate_factor_model(config: dict[str, Any]) -> dict[str, Any]:
    weights = validate_factor_weights(config.get("weights") if isinstance(config.get("weights"), dict) else DEFAULT_FACTOR_WEIGHTS)
    normalization_mode = str(config.get("normalization_mode") or "universe").strip().lower()
    if normalization_mode not in {"universe", "sector"}:
        raise ValueError("normalization_mode must be universe or sector.")
    method = str(config.get("selection_method") or "top_n").strip().lower()
    if method not in {"top_n", "top_percentile", "minimum_score", "all_eligible"}:
        raise ValueError("selection_method must be top_n, top_percentile, minimum_score, or all_eligible.")
    return {
        "enabled": bool(config.get("enabled", True)),
        "normalization_mode": normalization_mode,
        "weights": weights,
        "minimum_data_coverage_pct": _bounded_float(config.get("minimum_data_coverage_pct"), 60.0, 0.0, 100.0),
        "selection_method": method,
        "top_n": _bounded_int(config.get("top_n"), 10, 1, 50),
        "top_percentile": _bounded_float(config.get("top_percentile"), 30.0, 1.0, 100.0),
        "minimum_score": None if config.get("minimum_score") is None else _bounded_float(config.get("minimum_score"), 65.0, 0.0, 100.0),
    }


def validate_factor_weights(weights: dict[str, Any]) -> dict[str, float]:
    parsed = {group: float(weights.get(group, DEFAULT_FACTOR_WEIGHTS[group])) for group in GROUPS}
    if any(value < 0.0 for value in parsed.values()):
        raise ValueError("Factor weights must be non-negative.")
    total = sum(parsed.values())
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("Enabled factor weights must sum to 1.0.")
    return parsed


def validate_optimization_config(config: dict[str, Any]) -> dict[str, Any]:
    method = str(config.get("expected_return_method") or "historical").strip().lower()
    if method not in {"historical", "factor_tilted"}:
        raise ValueError("expected_return_method must be historical or factor_tilted.")
    objective = str(config.get("objective") or "max_sharpe").strip().lower()
    if objective not in {"max_sharpe", "min_volatility"}:
        raise ValueError("objective must be max_sharpe or min_volatility.")
    return {
        "objective": objective,
        "minimum_weight": _bounded_float(config.get("minimum_weight"), 0.0, 0.0, 1.0),
        "maximum_weight": _bounded_float(config.get("maximum_weight"), 0.25, 0.05, 1.0),
        "risk_free_rate": _bounded_float(config.get("risk_free_rate"), 0.04, 0.0, 0.25),
        "expected_return_method": method,
        "num_frontier_portfolios": _bounded_int(config.get("num_frontier_portfolios"), 3000, 100, 10000),
    }


def validate_score_tilt(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(config.get("enabled", False)),
        "strength": _bounded_float(config.get("strength"), 0.20, 0.0, 1.0),
        "maximum_adjustment_pct": _bounded_float(config.get("maximum_adjustment_pct"), 0.05, 0.0, 0.50),
    }


def validate_monte_carlo_config(config: dict[str, Any]) -> dict[str, Any]:
    scenarios = config.get("scenarios") if isinstance(config.get("scenarios"), list) else ["neutral", "bullish", "bearish", "crash"]
    cleaned = [str(item or "").strip().lower() for item in scenarios]
    if any(item not in {"neutral", "bullish", "bearish", "crash"} for item in cleaned):
        raise ValueError("Invalid Monte Carlo scenario.")
    return {
        "enabled": bool(config.get("enabled", True)),
        "days": _bounded_int(config.get("days"), 60, 1, 252),
        "simulations": _bounded_int(config.get("simulations"), 500, 100, 5000),
        "block_size": _bounded_int(config.get("block_size"), 5, 1, 20),
        "seed": None if config.get("seed") is None else int(config.get("seed", 42)),
        "scenarios": cleaned,
        "scenario_overrides": config.get("scenario_overrides") if isinstance(config.get("scenario_overrides"), dict) else {},
    }


def apply_factor_return_tilt(
    historical_returns: dict[str, float],
    selected: list[dict[str, Any]],
    strength: float = 0.20,
    maximum_adjustment_pct: float = 0.05,
) -> dict[str, float]:
    scores = np.array(
        [
            float(item["combined_portfolio_score"])
            if item.get("combined_portfolio_score") is not None
            else 50.0
            for item in selected
        ],
        dtype=float,
    )
    centered = (scores - 50.0) / 50.0
    max_adjustment = float(maximum_adjustment_pct)
    adjusted = {}
    for item, score_offset in zip(selected, centered, strict=True):
        ticker = item["ticker"]
        adjustment = max(-max_adjustment, min(max_adjustment, float(score_offset) * float(strength) * max_adjustment))
        adjusted[ticker] = float(historical_returns.get(ticker, 0.0)) + adjustment
    return adjusted


def _score_factor(
    records: list[dict[str, Any]],
    factor: str,
    higher_is_better: bool,
    normalization_mode: str,
    sector_min_count: int,
) -> None:
    groups: dict[str, list[dict[str, Any]]] = {"__universe__": records}
    if normalization_mode == "sector":
        groups = {}
        for item in records:
            groups.setdefault(str(item.get("sector") or "Unclassified"), []).append(item)

    for _group_name, items in groups.items():
        comparison = items if len(items) >= sector_min_count else records
        values = [_safe_float(item.get("raw_factor_values", {}).get(factor)) for item in comparison]
        valid = np.array([value for value in values if value is not None], dtype=float)
        if valid.size == 0:
            for item in items:
                item["normalized_factor_scores"][factor] = None
            continue
        clipped = _winsorized(valid)
        min_value = float(np.min(clipped))
        max_value = float(np.max(clipped))
        lookup = {}
        valid_index = 0
        for item, value in zip(comparison, values, strict=True):
            if value is None:
                lookup[item["ticker"]] = None
                continue
            clipped_value = float(clipped[valid_index])
            valid_index += 1
            if math.isclose(max_value, min_value):
                score = 50.0
            else:
                score = ((clipped_value - min_value) / (max_value - min_value)) * 100.0
            if not higher_is_better:
                score = 100.0 - score
            lookup[item["ticker"]] = _round(score)
        for item in items:
            item["normalized_factor_scores"][factor] = lookup.get(item["ticker"])


def _resolve_universe(symbols: list[str], sector: str | None, selection_mode: str) -> tuple[list[str], str | None, list[str]]:
    requested_sector = str(sector or "").strip() or None
    warnings: list[str] = []
    if requested_sector and (selection_mode == "sector" or not symbols):
        resolved = resolve_symbols_for_sector(requested_sector)
        if len(resolved) > 50:
            warnings.append("Prototype factor scoring is capped at the first 50 sector symbols to limit provider calls.")
            resolved = resolved[:50]
        return resolved, requested_sector, warnings
    normalized = []
    seen = set()
    for raw_symbol in symbols:
        symbol = str(raw_symbol or "").strip().upper()
        if ":" in symbol:
            symbol = symbol.split(":")[-1]
        if symbol and symbol not in seen:
            normalized.append(symbol)
            seen.add(symbol)
    valid = validate_symbols(normalized)
    invalid = [symbol for symbol in normalized if symbol not in set(valid)]
    if invalid:
        warnings.append(f"Rejected invalid universe symbols: {', '.join(invalid)}.")
    return valid, None, warnings


def _fetch_price_frame(
    symbols: list[str],
    lookback: str,
    resolution: str,
    finnhub_api_key: str | None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    series = []
    rejected = []
    for symbol in symbols:
        try:
            frame = fetch_multi_symbol_close_prices([symbol], lookback=lookback, resolution=resolution, finnhub_api_key=finnhub_api_key)
            series.append(frame[symbol])
        except Exception:
            rejected.append({"ticker": symbol, "reason": "Price history unavailable"})
    if not series:
        return pd.DataFrame(), rejected
    return pd.concat(series, axis=1, join="inner").dropna(how="any"), rejected


def _fundamental_values(metrics: dict[str, Any], earnings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "return_on_equity": _pick(metrics, "roeTTM", "roeRfy", "roeAnnual"),
        "return_on_assets": _pick(metrics, "roaTTM", "roaRfy", "roaAnnual"),
        "operating_margin": _pick(metrics, "operatingMarginTTM", "operatingMarginAnnual"),
        "net_profit_margin": _pick(metrics, "netProfitMarginTTM", "netProfitMarginAnnual"),
        "revenue_growth": _pick(metrics, "revenueGrowthTTMYoy", "revenueGrowthQuarterlyYoy"),
        "earnings_growth": _pick(metrics, "epsGrowthTTMYoy", "epsGrowthQuarterlyYoy"),
        "free_cash_flow_margin": _pick(metrics, "fcfMarginTTM", "freeCashFlowMarginTTM"),
        "debt_to_equity": _pick(metrics, "totalDebt/totalEquityAnnual", "totalDebt/totalEquityQuarterly"),
        "interest_coverage": _pick(metrics, "interestCoverageAnnual", "interestCoverageTTM"),
        "current_ratio": _pick(metrics, "currentRatioAnnual", "currentRatioQuarterly"),
        "earnings_consistency": _earnings_consistency(earnings),
    }


def _valuation_values(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "price_to_earnings": _positive_or_none(_pick(metrics, "peTTM", "peNormalizedAnnual")),
        "forward_price_to_earnings": _positive_or_none(_pick(metrics, "forwardPE", "forwardPe")),
        "price_to_book": _positive_or_none(_pick(metrics, "pbAnnual", "pbQuarterly")),
        "price_to_sales": _positive_or_none(_pick(metrics, "psTTM", "psAnnual")),
        "enterprise_value_to_ebitda": _positive_or_none(_pick(metrics, "evToEbitda", "evToEbitdaTTM")),
        "free_cash_flow_yield": _pick(metrics, "fcfYieldTTM", "freeCashFlowYieldTTM"),
    }


def _price_values(close_prices: pd.Series, metrics: dict[str, Any]) -> dict[str, Any]:
    close = pd.to_numeric(pd.Series(close_prices), errors="coerce").dropna()
    return {
        "return_1m": _period_return(close, 21),
        "return_3m": _period_return(close, 63),
        "return_6m": _period_return(close, 126),
        "return_12m": _period_return(close, 252),
        "return_excluding_latest_month": _skip_latest_month_return(close),
        "distance_50d_ma": _distance_to_ma(close, 50),
        "distance_200d_ma": _distance_to_ma(close, 200),
        "beta": _pick(metrics, "beta"),
    }


def _risk_values(close_prices: pd.Series, metrics: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    close = pd.to_numeric(pd.Series(close_prices), errors="coerce").dropna()
    returns = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    downside = returns[returns < 0]
    running_max = close.cummax()
    drawdown = close / running_max - 1.0
    debt = _safe_float(raw.get("debt_to_equity"))
    volatility = float(returns.std() * math.sqrt(TRADING_DAYS)) if len(returns) > 1 else None
    max_drawdown = abs(float(drawdown.min())) if len(drawdown) else None
    return {
        "historical_volatility": volatility,
        "maximum_drawdown": max_drawdown,
        "downside_volatility": float(downside.std() * math.sqrt(TRADING_DAYS)) if len(downside) > 1 else None,
        "earnings_variability": _pick(metrics, "epsInclExtraItemsCAGR5Y", "epsGrowth5Y"),
        "financial_distress_proxy": _mean_available([volatility, max_drawdown, debt]),
    }


def _analyst_values(metrics: dict[str, Any], recommendations: list[dict[str, Any]], earnings: list[dict[str, Any]]) -> dict[str, Any]:
    latest = recommendations[0] if recommendations and isinstance(recommendations[0], dict) else {}
    total = sum(_safe_float(latest.get(key)) or 0.0 for key in ("strongBuy", "buy", "hold", "sell", "strongSell"))
    recommendation_score = None
    if total:
        weighted = (
            5 * (_safe_float(latest.get("strongBuy")) or 0.0)
            + 4 * (_safe_float(latest.get("buy")) or 0.0)
            + 3 * (_safe_float(latest.get("hold")) or 0.0)
            + 2 * (_safe_float(latest.get("sell")) or 0.0)
            + 1 * (_safe_float(latest.get("strongSell")) or 0.0)
        ) / total
        recommendation_score = weighted / 5.0
    surprises = [_safe_float(item.get("surprisePercent")) for item in earnings if isinstance(item, dict)]
    surprises = [value for value in surprises if value is not None]
    return {
        "analyst_recommendation_score": recommendation_score,
        "earnings_estimate_revision": _pick(metrics, "epsEstYoyGrowth", "epsGrowthQuarterlyYoy"),
        "target_price_upside": _pick(metrics, "targetMeanPriceUpside", "targetPriceUpside"),
        "earnings_surprise": float(np.mean(surprises)) if surprises else None,
        "expected_earnings_change": _pick(metrics, "epsGrowthForward", "epsGrowthNextYear"),
    }


def _add_relative_strength(records: list[dict[str, Any]]) -> None:
    returns = [_safe_float(item["raw_factor_values"].get("return_6m")) for item in records]
    usable = [value for value in returns if value is not None]
    median = float(np.median(usable)) if usable else None
    for item, value in zip(records, returns, strict=True):
        item["raw_factor_values"]["relative_strength"] = None if value is None or median is None else value - median


def _historical_expected_returns(price_df: pd.DataFrame) -> dict[str, float]:
    returns = price_df.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna(how="any")
    return {str(symbol): float(returns[symbol].mean() * TRADING_DAYS) for symbol in returns.columns}


def _effective_weights(weights: dict[str, float], available_groups: dict[str, float]) -> dict[str, float]:
    total = sum(weights[group] for group in available_groups)
    if total <= 0:
        return {}
    return {group: weights[group] / total for group in available_groups}


def _weighted_subset(available_groups: dict[str, float], effective_weights: dict[str, float], groups: set[str]) -> float | None:
    subset = {group: available_groups[group] for group in groups if group in available_groups}
    total = sum(effective_weights[group] for group in subset)
    if not subset or total <= 0:
        return None
    return sum(value * (effective_weights[group] / total) for group, value in subset.items())


def _winsorized(values: np.ndarray) -> np.ndarray:
    if values.size < 3:
        return values
    lower, upper = np.percentile(values, [5, 95])
    return np.clip(values, lower, upper)


def _compact_scores(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "ticker",
        "company_name",
        "sector",
        "fundamental_quality_score",
        "valuation_score",
        "momentum_score",
        "analyst_score",
        "financial_risk_score",
        "quantitative_alpha_score",
        "combined_portfolio_score",
        "data_coverage_pct",
        "selection_status",
        "selection_reason",
        "expected_return_original",
        "expected_return_adjusted",
        "final_portfolio_weight",
    ]
    return [{key: item.get(key) for key in keys} for item in scored]


def _compact_optimization_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective": result.get("objective"),
        "weights": result.get("weights"),
        "metrics": result.get("metrics"),
        "artifact_id": result.get("artifact_id"),
        "artifact_url": result.get("artifact_url"),
    }


def _rejection(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"ticker": item.get("ticker"), "reason": reason}


def _error(message: str, errors: list[str], **extra: Any) -> dict[str, Any]:
    return {"status": "error", "message": message, "errors": errors, **extra}


def _pick(mapping: dict[str, Any], *keys: str) -> float | None:
    normalized = {_normalize_key(key): value for key, value in mapping.items()}
    for key in keys:
        value = _safe_float(normalized.get(_normalize_key(key)))
        if value is not None and math.isfinite(value):
            return value
    return None


def _normalize_key(key: str) -> str:
    return "".join(char.lower() for char in str(key) if char.isalnum())


def _positive_or_none(value: Any) -> float | None:
    parsed = _safe_float(value)
    return parsed if parsed is not None and parsed > 0 else None


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    parsed = _safe_float(value)
    if parsed is None:
        return default
    return max(minimum, min(maximum, parsed))


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _period_return(close: pd.Series, days: int) -> float | None:
    if len(close) <= days or float(close.iloc[-days - 1]) == 0.0:
        return None
    return float(close.iloc[-1] / close.iloc[-days - 1] - 1.0)


def _skip_latest_month_return(close: pd.Series) -> float | None:
    if len(close) <= 252 or float(close.iloc[-253]) == 0.0:
        return None
    return float(close.iloc[-22] / close.iloc[-253] - 1.0)


def _distance_to_ma(close: pd.Series, window: int) -> float | None:
    if len(close) < window:
        return None
    average = float(close.tail(window).mean())
    return None if average == 0.0 else float(close.iloc[-1] / average - 1.0)


def _earnings_consistency(earnings: list[dict[str, Any]]) -> float | None:
    actuals = [_safe_float(item.get("actual")) for item in earnings if isinstance(item, dict)]
    values = [value for value in actuals if value is not None]
    if len(values) < 4:
        return None
    positive = sum(1 for value in values[:8] if value > 0)
    return positive / min(len(values), 8)


def _mean_available(values: list[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return float(np.mean(usable)) if usable else None


def _round(value: Any, places: int = 4) -> float | None:
    parsed = _safe_float(value)
    return None if parsed is None else round(parsed, places)
