from __future__ import annotations

import math
import os
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from tools.cache import cache_key
from tools.formatting import save_artifact_json
from tools.market_data import fetch_finnhub_candles_with_metadata
from tools.monte_carlo import SCENARIO_NAMES, run_portfolio_scenario_monte_carlo
from tools.universe import resolve_market_data_symbol, resolve_symbols_for_sector, validate_symbols


TRADING_DAYS = 252
SUPPORTED_LOOKBACKS = {"1mo", "6mo", "1y", "2y", "5y"}
SUPPORTED_OBJECTIVES = {"max_sharpe", "min_volatility"}


def fetch_multi_symbol_close_prices(
    symbols: list[str],
    lookback: str = "2y",
    resolution: str = "D",
    finnhub_api_key: str | None = None,
) -> pd.DataFrame:
    series_by_symbol: list[pd.Series] = []
    for symbol in symbols:
        market_data_symbol = resolve_market_data_symbol(symbol)
        df, _metadata = fetch_finnhub_candles_with_metadata(
            market_data_symbol,
            lookback=lookback,
            resolution=resolution,
            api_key=finnhub_api_key,
        )
        close = df.set_index(pd.to_datetime(df["time"], utc=True))["close"].astype(float)
        close.name = symbol
        series_by_symbol.append(close)

    price_df = pd.concat(series_by_symbol, axis=1, join="inner")
    price_df = price_df.sort_index().replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if price_df.empty:
        raise ValueError("No overlapping close-price history was available for the selected symbols.")
    return price_df


def calculate_portfolio_metrics(
    weights,
    mean_returns,
    cov_matrix,
    risk_free_rate=0.0,
) -> tuple[float, float, float]:
    weights_array = np.asarray(weights, dtype=float)
    mean_array = np.asarray(mean_returns, dtype=float)
    cov_array = np.asarray(cov_matrix, dtype=float)
    expected_return = float(np.dot(weights_array, mean_array))
    volatility = float(np.sqrt(np.dot(weights_array.T, np.dot(cov_array, weights_array))))
    sharpe_ratio = 0.0 if volatility <= 0 else (expected_return - float(risk_free_rate)) / volatility
    return expected_return, volatility, float(sharpe_ratio)


def optimize_max_sharpe(
    price_df,
    risk_free_rate=0.0,
    allow_short=False,
    max_weight=1.0,
) -> dict[str, Any]:
    mean_returns, cov_matrix = _annualized_return_inputs(price_df)

    def objective(weights):
        _return, _volatility, sharpe = calculate_portfolio_metrics(
            weights,
            mean_returns,
            cov_matrix,
            risk_free_rate,
        )
        return -sharpe

    return _optimize(price_df.columns.tolist(), objective, mean_returns, cov_matrix, risk_free_rate, allow_short, max_weight)


def optimize_min_volatility(
    price_df,
    risk_free_rate=0.0,
    allow_short=False,
    max_weight=1.0,
) -> dict[str, Any]:
    mean_returns, cov_matrix = _annualized_return_inputs(price_df)

    def objective(weights):
        _return, volatility, _sharpe = calculate_portfolio_metrics(
            weights,
            mean_returns,
            cov_matrix,
            risk_free_rate,
        )
        return volatility

    return _optimize(price_df.columns.tolist(), objective, mean_returns, cov_matrix, risk_free_rate, allow_short, max_weight)


def generate_efficient_frontier(
    price_df,
    num_points=75,
    risk_free_rate=0.0,
    allow_short=False,
    max_weight=1.0,
    num_portfolios: int | None = None,
) -> list[dict[str, Any]]:
    if num_portfolios is not None:
        num_points = num_portfolios
    mean_returns, cov_matrix = _annualized_return_inputs(price_df)
    symbols = price_df.columns.tolist()
    min_return = _optimize_return_extreme(mean_returns, allow_short, max_weight, maximize=False)
    max_return = _optimize_return_extreme(mean_returns, allow_short, max_weight, maximize=True)
    if min_return is None or max_return is None or max_return < min_return:
        return []

    points: list[dict[str, Any]] = []
    target_returns = np.linspace(min_return, max_return, min(max(int(num_points), 50), 100))
    for target_return in target_returns:
        point = _optimize_for_target_return(
            symbols,
            mean_returns,
            cov_matrix,
            float(target_return),
            risk_free_rate,
            allow_short,
            max_weight,
        )
        if point:
            points.append(point)

    return _dedupe_and_sort_portfolio_points(points)


def generate_random_portfolios(
    price_df,
    num_portfolios=3000,
    risk_free_rate=0.0,
    allow_short=False,
    max_weight=1.0,
) -> list[dict[str, Any]]:
    mean_returns, cov_matrix = _annualized_return_inputs(price_df)
    symbols = price_df.columns.tolist()
    points: list[dict[str, Any]] = []
    for weights in _random_weight_samples(
        len(price_df.columns),
        int(num_portfolios),
        allow_short=bool(allow_short),
        max_weight=float(max_weight),
    ):
        expected_return, volatility, sharpe = calculate_portfolio_metrics(
            weights,
            mean_returns,
            cov_matrix,
            risk_free_rate,
        )
        point = _portfolio_point(symbols, weights, expected_return, volatility, sharpe, include_weights=True)
        if point:
            points.append(point)
    return points


def calculate_individual_assets(
    price_df,
    risk_free_rate=0.0,
) -> list[dict[str, Any]]:
    mean_returns, cov_matrix = _annualized_return_inputs(price_df)
    assets: list[dict[str, Any]] = []
    symbols = price_df.columns.tolist()
    for index, symbol in enumerate(symbols):
        weights = np.zeros(len(symbols), dtype=float)
        weights[index] = 1.0
        expected_return, volatility, sharpe = calculate_portfolio_metrics(
            weights,
            mean_returns,
            cov_matrix,
            risk_free_rate,
        )
        point = _portfolio_point(symbols, weights, expected_return, volatility, sharpe, include_weights=False)
        if point:
            point["ticker"] = symbol
            assets.append(point)
    return assets


def calculate_correlation_matrix(price_df) -> list[dict[str, Any]]:
    returns = _daily_returns(price_df)
    corr = returns.corr().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for symbol in corr.columns:
        row: dict[str, Any] = {"symbol": str(symbol)}
        for other_symbol in corr.columns:
            row[str(other_symbol)] = _round(float(corr.loc[symbol, other_symbol]), 4)
        rows.append(row)
    return rows


def calculate_weighted_portfolio_returns(
    price_df: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    returns = _daily_returns(price_df)
    weight_series = pd.Series(weights, dtype=float).reindex(returns.columns)
    if weight_series.isna().any():
        missing = [str(symbol) for symbol, value in weight_series.items() if pd.isna(value)]
        raise ValueError(f"Optimized weights were missing for: {', '.join(missing)}.")
    portfolio_returns = returns.mul(weight_series, axis=1).sum(axis=1)
    portfolio_returns = portfolio_returns.replace([np.inf, -np.inf], np.nan).dropna()
    if portfolio_returns.empty:
        raise ValueError("No valid weighted portfolio returns were available for scenario analysis.")
    portfolio_returns.name = "portfolio_return"
    return portfolio_returns


def run_markowitz_optimization_core(
    symbols: list[str] | None = None,
    sector: str | None = None,
    lookback: str = "2y",
    resolution: str = "D",
    objective: str = "max_sharpe",
    risk_free_rate: float = 0.0,
    allow_short: bool = False,
    max_weight: float = 0.6,
    num_frontier_portfolios: int = 3000,
    run_monte_carlo: bool = False,
    monte_carlo_days: int = 60,
    monte_carlo_simulations: int = 500,
    monte_carlo_block_size: int = 5,
    monte_carlo_seed: int | None = 42,
    monte_carlo_scenarios: list[str] | None = None,
    scenario_overrides: dict[str, dict[str, float]] | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    requested_symbols = _normalize_requested_symbols(symbols or [])
    requested_sector = str(sector or "").strip() or None
    selection_mode = "symbols"
    sector_used: str | None = None
    warnings: list[str] = []

    if requested_symbols:
        if requested_sector:
            warnings.append("Explicit symbols were provided, so sector was ignored.")
    elif requested_sector:
        requested_symbols = resolve_symbols_for_sector(requested_sector)
        if not requested_symbols:
            return {
                "status": "error",
                "message": f"No stocks found for sector {requested_sector}.",
                "errors": ["empty_sector"],
            }
        selection_mode = "sector"
        sector_used = requested_sector
    else:
        return {
            "status": "error",
            "message": "Provide either symbols or a sector for portfolio optimization.",
            "errors": ["missing_symbols_or_sector"],
        }

    if len(requested_symbols) < 2:
        raise ValueError("At least 2 symbols are required for portfolio optimization.")
    if len(requested_symbols) > 20:
        raise ValueError("At most 20 symbols are supported by this prototype.")

    lookback = _validate_lookback(lookback)
    resolution = _validate_resolution(resolution)
    objective = _validate_objective(objective)
    risk_free_rate = _validate_risk_free_rate(risk_free_rate)
    max_weight = _validate_max_weight(max_weight)
    num_frontier_portfolios = _validate_num_portfolios(num_frontier_portfolios)
    allow_short = bool(allow_short)

    used_symbols = validate_symbols(requested_symbols)
    invalid_symbols = [symbol for symbol in requested_symbols if symbol not in set(used_symbols)]
    if len(used_symbols) < 2:
        raise ValueError("At least 2 valid universe symbols are required for portfolio optimization.")
    if len(used_symbols) * max_weight < 1.0 - 1e-9:
        raise ValueError("max_weight is too low for the number of selected symbols.")

    price_df = fetch_multi_symbol_close_prices(
        used_symbols,
        lookback=lookback,
        resolution=resolution,
        finnhub_api_key=finnhub_api_key,
    )
    if price_df.shape[1] < 2:
        raise ValueError("At least 2 symbols returned usable close-price history.")
    if len(price_df) < 2:
        raise ValueError("Not enough overlapping close-price rows were available.")

    min_volatility = optimize_min_volatility(
        price_df,
        risk_free_rate=risk_free_rate,
        allow_short=allow_short,
        max_weight=max_weight,
    )
    max_sharpe = optimize_max_sharpe(
        price_df,
        risk_free_rate=risk_free_rate,
        allow_short=allow_short,
        max_weight=max_weight,
    )
    optimal = max_sharpe if objective == "max_sharpe" else min_volatility

    random_portfolios = generate_random_portfolios(
        price_df,
        num_portfolios=num_frontier_portfolios,
        risk_free_rate=risk_free_rate,
        allow_short=allow_short,
        max_weight=max_weight,
    )
    frontier = generate_efficient_frontier(
        price_df,
        num_points=75,
        risk_free_rate=risk_free_rate,
        allow_short=allow_short,
        max_weight=max_weight,
    )
    correlation_matrix = calculate_correlation_matrix(price_df)
    individual_assets = calculate_individual_assets(price_df, risk_free_rate=risk_free_rate)
    if invalid_symbols:
        warnings.append(f"Rejected invalid universe symbols: {', '.join(invalid_symbols)}.")
    if not frontier:
        warnings.append("Efficient frontier could not be computed.")

    scenario_analysis_compact: dict[str, Any] | None = None
    scenario_analysis_artifact: dict[str, Any] | None = None
    if run_monte_carlo:
        portfolio_returns = calculate_weighted_portfolio_returns(price_df, optimal["weights"])
        scenario_result = run_portfolio_scenario_monte_carlo(
            portfolio_returns,
            start_value=10000,
            days=monte_carlo_days,
            simulations=monte_carlo_simulations,
            block_size=monte_carlo_block_size,
            seed=monte_carlo_seed,
            scenarios=monte_carlo_scenarios or list(SCENARIO_NAMES),
            scenario_overrides=scenario_overrides or {},
        )
        scenario_analysis_compact = scenario_result["compact"]
        scenario_analysis_artifact = scenario_result["artifact"]

    artifact = {
        "symbols": used_symbols,
        "selection_mode": selection_mode,
        "sector": sector_used,
        "symbols_used": used_symbols,
        "objective": objective,
        "weights": optimal["weights"],
        "metrics": optimal["metrics"],
        "random_portfolios": random_portfolios,
        "efficient_frontier": frontier,
        "min_volatility_portfolio": min_volatility["portfolio"],
        "max_sharpe_portfolio": max_sharpe["portfolio"],
        "individual_assets": individual_assets,
        "correlation_matrix": correlation_matrix,
        "price_summary": _price_summary(price_df),
        "daily_returns_summary": _daily_returns_summary(price_df),
        "data_quality": _data_quality(price_df, requested_symbols, used_symbols),
        "warnings": warnings,
    }
    if scenario_analysis_artifact is not None:
        artifact["scenario_analysis"] = scenario_analysis_artifact

    artifact_path = save_artifact_json(_markowitz_run_id(used_symbols, objective), artifact)
    artifact_fields = _artifact_fields(artifact_path)

    response = {
        "status": "success",
        "tool": "run_markowitz_optimization",
        "objective": objective,
        "symbols": used_symbols,
        "selection_mode": selection_mode,
        "sector": sector_used,
        "symbols_used": used_symbols,
        "rejected_symbols": invalid_symbols,
        "weights": optimal["weights"],
        "metrics": optimal["metrics"],
        "selected_portfolio": optimal["portfolio"],
        "min_volatility_portfolio": min_volatility["portfolio"],
        "max_sharpe_portfolio": max_sharpe["portfolio"],
        "data_quality": _data_quality(price_df, requested_symbols, used_symbols),
        **artifact_fields,
        "warnings": warnings,
    }
    if scenario_analysis_compact is not None:
        response["scenario_analysis"] = scenario_analysis_compact
    return response


def _optimize(
    symbols: list[str],
    objective,
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float,
    allow_short: bool,
    max_weight: float,
) -> dict[str, Any]:
    symbol_count = len(symbols)
    initial_weights = np.repeat(1.0 / symbol_count, symbol_count)
    bounds = _bounds(symbol_count, allow_short=allow_short, max_weight=max_weight)
    constraints = ({"type": "eq", "fun": lambda weights: float(np.sum(weights) - 1.0)},)
    result = minimize(
        objective,
        initial_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    if not result.success:
        raise ValueError(f"Portfolio optimization failed: {result.message}")

    weights = _clean_weights(result.x)
    expected_return, volatility, sharpe = calculate_portfolio_metrics(
        weights,
        mean_returns,
        cov_matrix,
        risk_free_rate,
    )
    portfolio = _portfolio_point(symbols, weights, expected_return, volatility, sharpe, include_weights=True)
    if not portfolio:
        raise ValueError("Portfolio optimization returned non-finite metrics.")
    return {
        "weights": dict(portfolio["weights"]),
        "metrics": {
            "expected_annual_return_pct": _round_pct(expected_return),
            "annual_volatility_pct": _round_pct(volatility),
            "sharpe_ratio": _round(sharpe),
        },
        "portfolio": portfolio,
    }


def _optimize_for_target_return(
    symbols: list[str],
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    target_return: float,
    risk_free_rate: float,
    allow_short: bool,
    max_weight: float,
) -> dict[str, Any] | None:
    symbol_count = len(symbols)
    initial_weights = np.repeat(1.0 / symbol_count, symbol_count)
    bounds = _bounds(symbol_count, allow_short=allow_short, max_weight=max_weight)
    mean_array = np.asarray(mean_returns, dtype=float)
    cov_array = np.asarray(cov_matrix, dtype=float)
    constraints = (
        {"type": "eq", "fun": lambda weights: float(np.sum(weights) - 1.0)},
        {"type": "ineq", "fun": lambda weights: float(np.dot(weights, mean_array) - target_return)},
    )

    result = minimize(
        lambda weights: float(np.dot(weights.T, np.dot(cov_array, weights))),
        initial_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    if not result.success:
        return None

    weights = _clean_weights(result.x)
    expected_return, volatility, sharpe = calculate_portfolio_metrics(
        weights,
        mean_returns,
        cov_matrix,
        risk_free_rate,
    )
    return _portfolio_point(symbols, weights, expected_return, volatility, sharpe, include_weights=False)


def _optimize_return_extreme(
    mean_returns: pd.Series,
    allow_short: bool,
    max_weight: float,
    maximize: bool,
) -> float | None:
    symbol_count = len(mean_returns)
    initial_weights = np.repeat(1.0 / symbol_count, symbol_count)
    bounds = _bounds(symbol_count, allow_short=allow_short, max_weight=max_weight)
    mean_array = np.asarray(mean_returns, dtype=float)
    result = minimize(
        lambda weights: float((-1.0 if maximize else 1.0) * np.dot(weights, mean_array)),
        initial_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=({"type": "eq", "fun": lambda weights: float(np.sum(weights) - 1.0)},),
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    if not result.success:
        return None
    value = float(np.dot(_clean_weights(result.x), mean_array))
    return value if math.isfinite(value) else None


def _portfolio_point(
    symbols: list[str],
    weights: np.ndarray,
    expected_return: float,
    volatility: float,
    sharpe: float,
    include_weights: bool,
) -> dict[str, Any] | None:
    if not all(math.isfinite(float(value)) for value in (expected_return, volatility, sharpe)):
        return None
    point: dict[str, Any] = {
        "portfolio_volatility": _round(float(volatility), 6),
        "portfolio_return": _round(float(expected_return), 6),
        "sharpe_ratio": _round(float(sharpe), 4),
    }
    if include_weights:
        point["weights"] = {
            symbol: _round(float(weight), 6)
            for symbol, weight in zip(symbols, weights, strict=True)
        }
    return point


def _dedupe_and_sort_portfolio_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[float, float]] = set()
    for point in points:
        volatility = point.get("portfolio_volatility")
        portfolio_return = point.get("portfolio_return")
        if not isinstance(volatility, (int, float)) or not isinstance(portfolio_return, (int, float)):
            continue
        if not math.isfinite(float(volatility)) or not math.isfinite(float(portfolio_return)):
            continue
        key = (round(float(volatility), 6), round(float(portfolio_return), 6))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(point)
    return sorted(cleaned, key=lambda item: float(item["portfolio_volatility"]))


def _annualized_return_inputs(price_df: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    returns = _daily_returns(price_df)
    return returns.mean() * TRADING_DAYS, returns.cov() * TRADING_DAYS


def _daily_returns(price_df: pd.DataFrame) -> pd.DataFrame:
    returns = price_df.astype(float).pct_change(fill_method=None)
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if returns.empty:
        raise ValueError("Not enough price data to calculate daily returns.")
    return returns


def _random_weight_samples(
    symbol_count: int,
    num_portfolios: int,
    allow_short: bool,
    max_weight: float,
) -> list[np.ndarray]:
    if math.isclose(max_weight, 1.0 / symbol_count, rel_tol=0.0, abs_tol=1e-9):
        return [np.repeat(1.0 / symbol_count, symbol_count) for _ in range(num_portfolios)]

    rng = np.random.default_rng(42)
    samples: list[np.ndarray] = []
    attempts = 0
    max_attempts = max(10000, num_portfolios * 100)
    while len(samples) < num_portfolios and attempts < max_attempts:
        attempts += 1
        if allow_short:
            raw = rng.uniform(-max_weight, max_weight, symbol_count)
            weights = raw + ((1.0 - float(np.sum(raw))) / symbol_count)
        else:
            weights = rng.dirichlet(np.ones(symbol_count))
        if _weights_within_bounds(weights, allow_short=allow_short, max_weight=max_weight):
            samples.append(_clean_weights(weights))

    if not samples:
        samples.append(np.repeat(1.0 / symbol_count, symbol_count))
    return samples


def _bounds(symbol_count: int, allow_short: bool, max_weight: float) -> list[tuple[float, float]]:
    lower = -max_weight if allow_short else 0.0
    return [(lower, max_weight) for _ in range(symbol_count)]


def _weights_within_bounds(weights: np.ndarray, allow_short: bool, max_weight: float) -> bool:
    tolerance = 1e-9
    if abs(float(np.sum(weights)) - 1.0) > tolerance:
        return False
    if np.any(weights > max_weight + tolerance):
        return False
    if allow_short:
        return not np.any(weights < -max_weight - tolerance)
    return not np.any(weights < -tolerance)


def _clean_weights(weights: np.ndarray) -> np.ndarray:
    cleaned = np.asarray(weights, dtype=float)
    cleaned[np.abs(cleaned) < 1e-10] = 0.0
    total = float(np.sum(cleaned))
    if total:
        cleaned = cleaned / total
    return cleaned


def _normalize_requested_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols or []:
        cleaned = str(symbol or "").strip().upper()
        if ":" in cleaned:
            cleaned = cleaned.split(":")[-1]
        if cleaned and cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)
    return normalized


def _validate_lookback(value: str) -> str:
    lookback = str(value or "2y").strip().lower()
    if lookback not in SUPPORTED_LOOKBACKS:
        raise ValueError(f"Unsupported lookback '{value}'. Allowed values: {', '.join(sorted(SUPPORTED_LOOKBACKS))}.")
    return lookback


def _validate_resolution(value: str) -> str:
    resolution = str(value or "D").strip().upper()
    if resolution != "D":
        raise ValueError("Only daily resolution 'D' is supported.")
    return resolution


def _validate_objective(value: str) -> str:
    objective = str(value or "max_sharpe").strip().lower()
    if objective not in SUPPORTED_OBJECTIVES:
        raise ValueError("objective must be max_sharpe or min_volatility.")
    return objective


def _validate_risk_free_rate(value: float) -> float:
    parsed = 0.0 if value is None else float(value)
    if parsed < 0.0 or parsed > 0.25:
        raise ValueError("risk_free_rate must be between 0 and 0.25.")
    return parsed


def _validate_max_weight(value: float) -> float:
    parsed = 0.6 if value is None else float(value)
    if parsed < 0.05 or parsed > 1.0:
        raise ValueError("max_weight must be between 0.05 and 1.0.")
    return parsed


def _validate_num_portfolios(value: int) -> int:
    parsed = 3000 if value is None else int(value)
    if parsed < 100 or parsed > 10000:
        raise ValueError("num_frontier_portfolios must be between 100 and 10000.")
    return parsed


def _price_summary(price_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in price_df.columns:
        start_price = float(price_df[symbol].iloc[0])
        end_price = float(price_df[symbol].iloc[-1])
        total_return = (end_price / start_price) - 1.0 if start_price else 0.0
        rows.append(
            {
                "symbol": str(symbol),
                "start_price": _round(start_price),
                "end_price": _round(end_price),
                "total_return_pct": _round_pct(total_return),
                "rows": int(price_df[symbol].count()),
            }
        )
    return rows


def _daily_returns_summary(price_df: pd.DataFrame) -> list[dict[str, Any]]:
    returns = _daily_returns(price_df)
    rows: list[dict[str, Any]] = []
    for symbol in returns.columns:
        rows.append(
            {
                "symbol": str(symbol),
                "mean_daily_return_pct": _round_pct(float(returns[symbol].mean())),
                "annual_return_pct": _round_pct(float(returns[symbol].mean()) * TRADING_DAYS),
                "annual_volatility_pct": _round_pct(float(returns[symbol].std()) * math.sqrt(TRADING_DAYS)),
            }
        )
    return rows


def _data_quality(
    price_df: pd.DataFrame,
    requested_symbols: list[str],
    used_symbols: list[str],
) -> dict[str, Any]:
    return {
        "symbols_requested": len(requested_symbols),
        "symbols_used": len(used_symbols),
        "start_date": price_df.index[0].date().isoformat(),
        "end_date": price_df.index[-1].date().isoformat(),
        "rows_used": int(len(price_df)),
    }


def _markowitz_run_id(symbols: list[str], objective: str) -> str:
    unique = uuid.uuid4().hex[:8]
    key = cache_key(",".join(symbols), objective, unique)[:6]
    return f"markowitz_{key}"


def _artifact_fields(artifact_path: str) -> dict[str, Any]:
    artifact_id = Path(artifact_path).stem
    fields: dict[str, Any] = {
        "artifact_path": artifact_path,
        "artifact_id": artifact_id,
    }
    public_base_url = os.getenv("MCP_PUBLIC_BASE_URL", "").rstrip("/")
    if public_base_url:
        fields["artifact_url"] = f"{public_base_url}/artifacts/{artifact_id}"
    return fields


def _round(value: float, places: int = 4) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(float(value), places)


def _round_pct(value: float) -> float:
    return _round(float(value) * 100.0)
