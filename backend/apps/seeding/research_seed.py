from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


SeedJobKind = Literal["backtest", "markowitz"]

SELECTED_SYMBOLS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "META",
    "AMZN",
    "TSLA",
    "AVGO",
    "JPM",
    "BAC",
    "GS",
    "V",
    "MA",
    "XOM",
    "CVX",
    "COP",
    "JNJ",
    "LLY",
    "UNH",
    "ABBV",
    "MRK",
    "HD",
    "NKE",
    "SBUX",
    "MCD",
    "WMT",
    "AMD",
    "CRM",
    "CAT",
    "BA",
)

LOOKBACKS: tuple[str, ...] = ("1y", "2y", "5y")
RESOLUTION = "D"
INITIAL_CASH = 10000.0
FEES = 0.001
MONTE_CARLO_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "days": 60,
    "simulations": 500,
    "method": "bootstrap",
}


@dataclass(frozen=True)
class ParameterSet:
    label: str
    run_slug: str
    parameters: dict[str, Any]


STRATEGY_PARAMETER_SETS: dict[str, tuple[ParameterSet, ...]] = {
    "sma_crossover": (
        ParameterSet("10/30", "10_30", {"fast_window": 10, "slow_window": 30}),
        ParameterSet("20/50", "20_50", {"fast_window": 20, "slow_window": 50}),
        ParameterSet("50/200", "50_200", {"fast_window": 50, "slow_window": 200}),
    ),
    "rsi_mean_reversion": (
        ParameterSet("14/30/70", "14_30_70", {"rsi_window": 14, "lower": 30, "upper": 70}),
        ParameterSet("10/25/75", "10_25_75", {"rsi_window": 10, "lower": 25, "upper": 75}),
        ParameterSet("21/35/65", "21_35_65", {"rsi_window": 21, "lower": 35, "upper": 65}),
    ),
    "bollinger_reversion": (
        ParameterSet("20/2.0", "20_2_0", {"window": 20, "std_dev": 2.0}),
        ParameterSet("20/2.5", "20_2_5", {"window": 20, "std_dev": 2.5}),
        ParameterSet("30/2.0", "30_2_0", {"window": 30, "std_dev": 2.0}),
    ),
}


@dataclass(frozen=True)
class PortfolioSeed:
    name: str
    symbols: tuple[str, ...]


PORTFOLIOS: tuple[PortfolioSeed, ...] = (
    PortfolioSeed("Mega Tech", ("AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "AMD")),
    PortfolioSeed("Financials", ("JPM", "BAC", "GS", "V", "MA")),
    PortfolioSeed("Energy", ("XOM", "CVX", "COP")),
    PortfolioSeed("Healthcare", ("JNJ", "LLY", "UNH", "ABBV", "MRK")),
    PortfolioSeed("Consumer", ("HD", "NKE", "SBUX", "MCD", "WMT")),
    PortfolioSeed("Industrials", ("CAT", "BA")),
    PortfolioSeed("Balanced Large Cap", ("AAPL", "MSFT", "JPM", "XOM", "JNJ", "HD", "CAT")),
    PortfolioSeed("Growth Basket", ("NVDA", "TSLA", "AMD", "CRM", "META", "AMZN")),
)

MARKOWITZ_OBJECTIVES: tuple[str, ...] = ("max_sharpe", "min_volatility")
MARKOWITZ_MAX_WEIGHTS: tuple[float, ...] = (0.3, 0.5)
MARKOWITZ_SETTINGS: dict[str, Any] = {
    "resolution": RESOLUTION,
    "risk_free_rate": 0.0,
    "allow_short": False,
    "num_frontier_portfolios": 3000,
}


@dataclass(frozen=True)
class SeedJob:
    kind: SeedJobKind
    run_id: str
    payload: dict[str, Any]
    symbol: str | None = None
    portfolio_name: str | None = None
    strategy: str | None = None
    parameter_label: str | None = None
    lookback: str | None = None
    objective: str | None = None
    max_weight: float | None = None

    @property
    def table_name(self) -> str:
        if self.kind == "backtest":
            return "backtest_runs"
        return "portfolio_optimization_runs"

    @property
    def description(self) -> str:
        if self.kind == "backtest":
            return (
                f"{self.symbol} {self.strategy} "
                f"{self.parameter_label} {self.lookback}"
            )
        return (
            f"{self.portfolio_name} {self.objective} "
            f"{self.lookback} max_weight={_format_float(self.max_weight)}"
        )


@dataclass(frozen=True)
class SeedPlan:
    jobs: list[SeedJob]
    missing_symbols: tuple[str, ...]
    skipped_portfolios: tuple[str, ...]

    @property
    def backtest_count(self) -> int:
        return sum(1 for job in self.jobs if job.kind == "backtest")

    @property
    def markowitz_count(self) -> int:
        return sum(1 for job in self.jobs if job.kind == "markowitz")

    @property
    def total_count(self) -> int:
        return len(self.jobs)


def generate_seed_plan(
    available_symbols: set[str] | None = None,
    *,
    include_backtests: bool = True,
    include_markowitz: bool = True,
) -> SeedPlan:
    selected_symbols = _selected_symbols_in_universe(available_symbols)
    selected_symbol_set = set(selected_symbols)
    missing_symbols = tuple(symbol for symbol in SELECTED_SYMBOLS if symbol not in selected_symbol_set)
    jobs: list[SeedJob] = []
    skipped_portfolios: list[str] = []

    if include_backtests:
        for symbol in selected_symbols:
            for strategy, parameter_sets in STRATEGY_PARAMETER_SETS.items():
                for parameter_set in parameter_sets:
                    for lookback in LOOKBACKS:
                        run_id = make_backtest_run_id(
                            symbol=symbol,
                            strategy=strategy,
                            parameter_slug=parameter_set.run_slug,
                            parameters=parameter_set.parameters,
                            lookback=lookback,
                        )
                        payload = {
                            "run_id": run_id,
                            "request_type": "strategy_backtest",
                            "symbol": symbol,
                            "strategy": strategy,
                            "parameters": dict(parameter_set.parameters),
                            "lookback": lookback,
                            "resolution": RESOLUTION,
                            "initial_cash": INITIAL_CASH,
                            "fees": FEES,
                            "monte_carlo": dict(MONTE_CARLO_SETTINGS),
                        }
                        jobs.append(
                            SeedJob(
                                kind="backtest",
                                run_id=run_id,
                                payload=payload,
                                symbol=symbol,
                                strategy=strategy,
                                parameter_label=parameter_set.label,
                                lookback=lookback,
                            )
                        )

    if include_markowitz:
        for portfolio in PORTFOLIOS:
            portfolio_symbols = tuple(symbol for symbol in portfolio.symbols if symbol in selected_symbol_set)
            if len(portfolio_symbols) < 2:
                skipped_portfolios.append(portfolio.name)
                continue
            for objective in MARKOWITZ_OBJECTIVES:
                for lookback in LOOKBACKS:
                    for max_weight in MARKOWITZ_MAX_WEIGHTS:
                        run_id = make_markowitz_run_id(
                            portfolio_name=portfolio.name,
                            symbols=portfolio_symbols,
                            objective=objective,
                            lookback=lookback,
                            max_weight=max_weight,
                            risk_free_rate=MARKOWITZ_SETTINGS["risk_free_rate"],
                            allow_short=MARKOWITZ_SETTINGS["allow_short"],
                            num_frontier_portfolios=MARKOWITZ_SETTINGS["num_frontier_portfolios"],
                        )
                        payload = {
                            "run_id": run_id,
                            "request_type": "portfolio_optimization",
                            "portfolio_name": portfolio.name,
                            "symbols": list(portfolio_symbols),
                            "sector": "",
                            "lookback": lookback,
                            "objective": objective,
                            "max_weight": max_weight,
                            **MARKOWITZ_SETTINGS,
                        }
                        jobs.append(
                            SeedJob(
                                kind="markowitz",
                                run_id=run_id,
                                payload=payload,
                                portfolio_name=portfolio.name,
                                lookback=lookback,
                                objective=objective,
                                max_weight=max_weight,
                            )
                        )

    return SeedPlan(
        jobs=jobs,
        missing_symbols=missing_symbols,
        skipped_portfolios=tuple(skipped_portfolios),
    )


def make_backtest_run_id(
    *,
    symbol: str,
    strategy: str,
    parameter_slug: str,
    parameters: dict[str, Any],
    lookback: str,
) -> str:
    identity = {
        "symbol": symbol,
        "strategy": strategy,
        "parameters": parameters,
        "lookback": lookback,
        "resolution": RESOLUTION,
        "initial_cash": INITIAL_CASH,
        "fees": FEES,
        "monte_carlo": MONTE_CARLO_SETTINGS,
    }
    digest = _stable_digest(identity)
    return f"seed_bt_{_slug(symbol)}_{_slug(strategy)}_{_slug(lookback)}_{parameter_slug}_{digest}"


def make_markowitz_run_id(
    *,
    portfolio_name: str,
    symbols: tuple[str, ...],
    objective: str,
    lookback: str,
    max_weight: float,
    risk_free_rate: float,
    allow_short: bool,
    num_frontier_portfolios: int,
) -> str:
    identity = {
        "portfolio_name": portfolio_name,
        "symbols": list(symbols),
        "objective": objective,
        "lookback": lookback,
        "max_weight": max_weight,
        "risk_free_rate": risk_free_rate,
        "allow_short": allow_short,
        "num_frontier_portfolios": num_frontier_portfolios,
    }
    digest = _stable_digest(identity)
    return (
        f"seed_mk_{_slug(portfolio_name)}_{_slug(objective)}_"
        f"{_slug(lookback)}_{_slug(_format_float(max_weight))}_{digest}"
    )


def load_universe_symbols() -> tuple[set[str] | None, Path | None, list[Path]]:
    attempted_paths = _universe_search_paths()
    for path in attempted_paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        return _extract_universe_symbols(data), path, attempted_paths
    return None, None, attempted_paths


def _selected_symbols_in_universe(available_symbols: set[str] | None) -> tuple[str, ...]:
    if available_symbols is None:
        return SELECTED_SYMBOLS
    available = {symbol.upper() for symbol in available_symbols}
    return tuple(symbol for symbol in SELECTED_SYMBOLS if symbol in available)


def _extract_universe_symbols(data: Any) -> set[str]:
    symbols: set[str] = set()
    if isinstance(data, dict):
        raw_symbols = data.get("symbols")
        if isinstance(raw_symbols, list):
            symbols.update(_normalize_symbol(value) for value in raw_symbols)
        raw_tickers = data.get("tickers")
        if isinstance(raw_tickers, list):
            for item in raw_tickers:
                if isinstance(item, dict):
                    symbols.add(_normalize_symbol(item.get("symbol") or item.get("ticker")))
                else:
                    symbols.add(_normalize_symbol(item))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                symbols.add(_normalize_symbol(item.get("symbol") or item.get("ticker")))
            else:
                symbols.add(_normalize_symbol(item))
    return {symbol for symbol in symbols if symbol}


def _universe_search_paths() -> list[Path]:
    paths: list[Path] = []
    explicit = os.getenv("SEED_UNIVERSE_FILE")
    if explicit:
        paths.append(Path(explicit))

    try:
        from django.conf import settings

        backend_dir = Path(settings.BASE_DIR)
        paths.extend(
            [
                backend_dir / "mcp" / "us_stocks_only_universe.json",
                backend_dir.parent / "mcp" / "us_stocks_only_universe.json",
            ]
        )
    except Exception:
        pass

    cwd = Path.cwd()
    paths.extend(
        [
            cwd / "mcp" / "us_stocks_only_universe.json",
            cwd.parent / "mcp" / "us_stocks_only_universe.json",
        ]
    )

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            deduped.append(path)
            seen.add(key)
    return deduped


def _stable_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _slug(value: Any) -> str:
    text = str(value or "").strip()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return slug or "value"


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):g}"
