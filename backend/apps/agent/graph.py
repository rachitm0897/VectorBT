import json
import re
from functools import lru_cache
from typing import Any, TypedDict

from django.conf import settings
from langgraph.graph import END, StateGraph
from openai import OpenAI, OpenAIError

from apps.agent.cache import load_parsed_request, save_parsed_request
from apps.api_keys import resolve_chat_api_key, resolve_chat_model, resolve_chat_url
from apps.backtesting.engine import BacktestExecutionError, run_backtest, run_portfolio_optimization
from apps.backtesting.serializers import BacktestRequestSerializer, PortfolioOptimizationRequestSerializer
from apps.market_data.finnhub import MarketDataError
from apps.market_data.symbols import normalize_symbol
from apps.strategies.registry import SUPPORTED_STRATEGIES, StrategyValidationError


DEFAULTS = {
    "strategy": "sma_crossover",
    "lookback": "2y",
    "resolution": "D",
    "initial_cash": 10000.0,
    "fees": 0.001,
    "monte_carlo": {
        "enabled": True,
        "days": 60,
        "simulations": 500,
        "method": "bootstrap",
    },
}

PORTFOLIO_DEFAULTS = {
    "lookback": "2y",
    "resolution": "D",
    "objective": "max_sharpe",
    "risk_free_rate": 0.0,
    "allow_short": False,
    "max_weight": 0.6,
    "num_frontier_portfolios": 3000,
}

STRATEGY_DEFAULT_PARAMETERS = {
    "sma_crossover": {"fast_window": 20, "slow_window": 50},
    "rsi_mean_reversion": {"rsi_window": 14, "lower": 30, "upper": 70},
    "bollinger_reversion": {"window": 20, "std_dev": 2},
}

STRATEGY_ALIASES = {
    "sma": "sma_crossover",
    "ma": "sma_crossover",
    "moving_average": "sma_crossover",
    "moving_average_crossover": "sma_crossover",
    "sma_crossover": "sma_crossover",
    "rsi": "rsi_mean_reversion",
    "rsi_mean_reversion": "rsi_mean_reversion",
    "bollinger": "bollinger_reversion",
    "bollinger_bands": "bollinger_reversion",
    "bollinger_reversion": "bollinger_reversion",
}

PARSER_PROMPT = """Return JSON only. Parse a stock research request.
Request types: strategy_backtest or portfolio_optimization.
Strategies: sma_crossover fast_window=20 slow_window=50; rsi_mean_reversion rsi_window=14 lower=30 upper=70; bollinger_reversion window=20 std_dev=2.
Names: Apple=AAPL Tesla=TSLA Nvidia=NVDA Microsoft=MSFT Amazon=AMZN Meta/Facebook=META Google/Alphabet=GOOGL Netflix=NFLX.
Backtest defaults: strategy=sma_crossover lookback=2y resolution=D initial_cash=10000 fees=0.001 monte_carlo={enabled:true,days:60,simulations:500,method:bootstrap}.
Portfolio defaults: lookback=2y resolution=D objective=max_sharpe risk_free_rate=0 allow_short=false max_weight=0.6 num_frontier_portfolios=3000.
Lookback allowed: 1mo,6mo,1y,2y,5y. Use null when symbol missing.
For portfolio requests output symbols as tickers. If sector-only, output sector and symbols=[].
Examples: "Optimize AAPL, MSFT, NVDA and GOOGL using Markowitz" => request_type=portfolio_optimization symbols=["AAPL","MSFT","NVDA","GOOGL"] objective=max_sharpe.
"Create a max Sharpe portfolio with Apple, Microsoft, Nvidia and Google" => request_type=portfolio_optimization symbols=["AAPL","MSFT","NVDA","GOOGL"] objective=max_sharpe.
"Find minimum volatility portfolio using AAPL MSFT AMZN META over 2 years" => request_type=portfolio_optimization symbols=["AAPL","MSFT","AMZN","META"] lookback=2y objective=min_volatility.
"Create a max Sharpe portfolio from Technology stocks using Markowitz" => request_type=portfolio_optimization sector="Technology" symbols=[] objective=max_sharpe.
"Find minimum volatility portfolio from Healthcare stocks" => request_type=portfolio_optimization sector="Healthcare" symbols=[] objective=min_volatility.
Do not invent unsupported tools or request types.
Output keys for backtests: request_type,symbol,strategy,parameters,lookback,resolution,initial_cash,fees,monte_carlo.
Output keys for portfolios: request_type,symbols,sector,lookback,resolution,objective,risk_free_rate,allow_short,max_weight,num_frontier_portfolios."""


class AgentState(TypedDict, total=False):
    message: str
    chat_url: str
    chat_api_key: str
    model: str
    finnhub_api_key: str
    parsed_request: dict[str, Any]
    validated_request: dict[str, Any]
    backtest_result: dict[str, Any]
    portfolio_result: dict[str, Any]
    diagnostics: dict[str, Any]
    result_type: str
    assistant_message: str
    status: str
    warnings: list[str]
    errors: list[str]
    missing_fields: list[str]


def run_chat_workflow(
    message: str,
    chat_api_key: str | None = None,
    chat_url: str | None = None,
    model: str | None = None,
    finnhub_api_key: str | None = None,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_model: str | None = None,
) -> dict[str, Any]:
    state = _graph().invoke(
        {
            "message": message,
            "chat_url": chat_url or openai_base_url or settings.DEFAULT_CHAT_URL,
            "chat_api_key": chat_api_key or openai_api_key or "",
            "model": model or openai_model or settings.DEFAULT_CHAT_MODEL,
            "finnhub_api_key": finnhub_api_key or "",
            "status": "running",
            "warnings": [],
            "errors": [],
        }
    )
    return {
        "status": state.get("status", "error"),
        "assistant_message": state.get("assistant_message", "Chat request failed."),
        "parsed_request": state.get("validated_request") or state.get("parsed_request") or {},
        "result_type": state.get("result_type") or (state.get("validated_request") or {}).get("request_type"),
        "backtest_result": state.get("backtest_result") or {},
        "portfolio_result": state.get("portfolio_result") or {},
        "diagnostics": _result_diagnostics(state),
        "warnings": state.get("warnings", []),
        "errors": state.get("errors", []),
        "missing_fields": state.get("missing_fields", []),
    }


def parse_request_node(state: AgentState) -> AgentState:
    api_key = resolve_chat_api_key(state.get("chat_api_key"))
    if not api_key:
        return {
            **state,
            "status": "error",
            "errors": ["missing_chat_api_key"],
            "assistant_message": "Chat API key is required for natural language parsing.",
        }

    cached = load_parsed_request(state["message"])
    if cached is not None:
        return {**state, "parsed_request": cached}

    chat_url = resolve_chat_url(state.get("chat_url"))
    model = resolve_chat_model(state.get("model"))

    try:
        parsed = _call_parser_llm(state["message"], api_key=api_key, chat_url=chat_url, model=model)
    except (OpenAIError, ValueError, json.JSONDecodeError) as exc:
        return {
            **state,
            "status": "error",
            "errors": ["parse_failed"],
            "assistant_message": f"Could not parse the request: {exc}",
        }

    save_parsed_request(state["message"], parsed)
    return {**state, "parsed_request": parsed}


def validate_request_node(state: AgentState) -> AgentState:
    if state.get("status") == "error":
        return state

    parsed = state.get("parsed_request") or {}
    warnings = list(state.get("warnings", []))
    request_type = _normalize_request_type(parsed)

    if request_type == "portfolio_optimization":
        symbols = _normalize_symbols(parsed.get("symbols") or parsed.get("symbol"))
        sector = _normalize_sector(parsed.get("sector"))
        if len(symbols) < 2 and not sector:
            return {
                **state,
                "status": "needs_input",
                "result_type": "portfolio_optimization",
                "missing_fields": ["symbols"],
                "assistant_message": "Please select at least two valid US stock tickers or choose a sector for portfolio optimization.",
            }

        request_data = {
            "request_type": "portfolio_optimization",
            "symbols": symbols,
            "sector": sector,
            "lookback": _normalize_portfolio_lookback(parsed.get("lookback")),
            "resolution": "D",
            "objective": _normalize_objective(parsed.get("objective")),
            "risk_free_rate": _bounded_float_inclusive(
                parsed.get("risk_free_rate"),
                PORTFOLIO_DEFAULTS["risk_free_rate"],
                0.0,
                0.25,
            ),
            "allow_short": bool(parsed.get("allow_short", PORTFOLIO_DEFAULTS["allow_short"])),
            "max_weight": _bounded_float_inclusive(
                parsed.get("max_weight"),
                PORTFOLIO_DEFAULTS["max_weight"],
                0.05,
                1.0,
            ),
            "num_frontier_portfolios": _bounded_int(
                parsed.get("num_frontier_portfolios"),
                PORTFOLIO_DEFAULTS["num_frontier_portfolios"],
                100,
                10000,
            ),
        }
        serializer = PortfolioOptimizationRequestSerializer(data=request_data)
        if not serializer.is_valid():
            return {
                **state,
                "status": "error",
                "result_type": "portfolio_optimization",
                "errors": ["invalid_parsed_request"],
                "assistant_message": "The parsed portfolio request was invalid after applying defaults.",
            }
        validated = dict(serializer.validated_data)
        validated["request_type"] = "portfolio_optimization"
        return {**state, "validated_request": validated, "result_type": "portfolio_optimization", "warnings": warnings}

    symbol = normalize_symbol(str(parsed.get("symbol") or ""))

    if not _looks_like_ticker(symbol):
        return {
            **state,
            "status": "needs_input",
            "missing_fields": ["symbol"],
            "assistant_message": "Please provide a valid US stock ticker.",
        }

    strategy = _normalize_strategy(parsed.get("strategy"))
    if strategy not in SUPPORTED_STRATEGIES:
        strategy = DEFAULTS["strategy"]
        warnings.append("Unsupported strategy requested; using default SMA crossover.")

    parameters = _defaulted_parameters(strategy, parsed.get("parameters"))
    monte_carlo = _defaulted_monte_carlo(parsed.get("monte_carlo"))
    request_data = {
        "request_type": "strategy_backtest",
        "symbol": symbol,
        "strategy": strategy,
        "parameters": parameters,
        "lookback": _normalize_lookback(parsed.get("lookback")),
        "resolution": "D",
        "initial_cash": _positive_float(parsed.get("initial_cash"), DEFAULTS["initial_cash"]),
        "fees": _non_negative_float(parsed.get("fees"), DEFAULTS["fees"]),
        "monte_carlo": monte_carlo,
    }

    serializer = BacktestRequestSerializer(data=request_data)
    if not serializer.is_valid():
        return {
            **state,
            "status": "error",
            "errors": ["invalid_parsed_request"],
            "assistant_message": "The parsed request was invalid after applying defaults.",
        }

    validated = dict(serializer.validated_data)
    validated["request_type"] = "strategy_backtest"
    return {**state, "validated_request": validated, "result_type": "strategy_backtest", "warnings": warnings}


def run_backtest_node(state: AgentState) -> AgentState:
    if state.get("status") in {"error", "needs_input"}:
        return state

    try:
        if state.get("result_type") == "portfolio_optimization":
            result = run_portfolio_optimization(
                state["validated_request"],
                finnhub_api_key=state.get("finnhub_api_key"),
            )
            return {
                **state,
                "status": "success",
                "portfolio_result": result.get("portfolio_result") or result,
                "diagnostics": result.get("diagnostics") or {},
                "warnings": [*state.get("warnings", []), *(result.get("warnings") or [])],
            }

        result = run_backtest(state["validated_request"], finnhub_api_key=state.get("finnhub_api_key"))
    except MarketDataError as exc:
        return {**state, "status": "error", "errors": [exc.code], "assistant_message": str(exc)}
    except StrategyValidationError as exc:
        return {**state, "status": "error", "errors": [exc.code], "assistant_message": str(exc)}
    except BacktestExecutionError as exc:
        return {**state, "status": "error", "errors": [exc.code], "assistant_message": str(exc)}
    except Exception:
        return {
            **state,
            "status": "error",
            "errors": ["backtest_failed"],
            "assistant_message": "Backtest failed unexpectedly.",
        }

    return {**state, "status": "success", "backtest_result": result}


def format_response_node(state: AgentState) -> AgentState:
    if state.get("assistant_message"):
        return state

    if state.get("status") == "success":
        request = state.get("validated_request", {})
        if state.get("result_type") == "portfolio_optimization":
            if request.get("sector") and not request.get("symbols"):
                message = f"Portfolio optimization completed for the {request.get('sector')} sector."
            else:
                symbols = ", ".join(request.get("symbols") or [])
                message = f"Portfolio optimization completed for {symbols}."
            return {**state, "assistant_message": message}

        strategy_label = _strategy_label(str(request.get("strategy", DEFAULTS["strategy"])))
        message = f"Backtest completed for {request.get('symbol')} using {strategy_label}."
        return {**state, "assistant_message": message}

    return {**state, "assistant_message": "Chat request failed."}


@lru_cache(maxsize=1)
def _graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("parse_request_node", parse_request_node)
    workflow.add_node("validate_request_node", validate_request_node)
    workflow.add_node("run_backtest_node", run_backtest_node)
    workflow.add_node("format_response_node", format_response_node)
    workflow.set_entry_point("parse_request_node")
    workflow.add_edge("parse_request_node", "validate_request_node")
    workflow.add_edge("validate_request_node", "run_backtest_node")
    workflow.add_edge("run_backtest_node", "format_response_node")
    workflow.add_edge("format_response_node", END)
    return workflow.compile()


def _call_parser_llm(message: str, api_key: str, chat_url: str, model: str) -> dict[str, Any]:
    client = OpenAI(api_key=api_key, base_url=chat_url)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=520,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PARSER_PROMPT},
            {"role": "user", "content": message},
        ],
    )
    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Parser did not return a JSON object.")
    return parsed


def _result_diagnostics(state: AgentState) -> dict[str, Any]:
    diagnostics = state.get("diagnostics")
    if isinstance(diagnostics, dict):
        return diagnostics
    backtest_result = state.get("backtest_result") or {}
    if isinstance(backtest_result.get("diagnostics"), dict):
        return backtest_result["diagnostics"]
    return {}


def _normalize_request_type(parsed: dict[str, Any]) -> str:
    request_type = str(parsed.get("request_type") or "").strip().lower()
    if request_type in {"portfolio", "portfolio_optimizer", "markowitz", "markowitz_optimization"}:
        return "portfolio_optimization"
    if request_type in {"strategy_backtest", "backtest", "strategy"}:
        return "strategy_backtest"
    if parsed.get("symbols") or parsed.get("sector") or parsed.get("objective") in {"max_sharpe", "min_volatility"}:
        return "portfolio_optimization"
    return "strategy_backtest"


def _normalize_symbols(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_symbols = value
    elif isinstance(value, str) and re.search(r"[,;]|\s+and\s+|\s+", value.strip(), flags=re.IGNORECASE):
        raw_symbols = [part for part in re.split(r"[,;]|\s+and\s+|\s+", value) if part.strip()]
    else:
        raw_symbols = [value]
    symbols: list[str] = []
    seen: set[str] = set()
    for raw_symbol in raw_symbols:
        symbol = normalize_symbol(str(raw_symbol or ""))
        if ":" in symbol:
            symbol = symbol.split(":")[-1]
        if _looks_like_ticker(symbol) and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    return symbols


def _normalize_portfolio_lookback(value: Any) -> str:
    lookback = str(value or PORTFOLIO_DEFAULTS["lookback"]).strip().lower()
    aliases = {
        "1m": "1mo",
        "1month": "1mo",
        "1_month": "1mo",
        "6m": "6mo",
        "6month": "6mo",
        "6_month": "6mo",
        "1yr": "1y",
        "1year": "1y",
        "1_year": "1y",
        "2yr": "2y",
        "2year": "2y",
        "2_year": "2y",
        "5yr": "5y",
        "5year": "5y",
        "5_year": "5y",
    }
    lookback = aliases.get(lookback, lookback)
    return lookback if lookback in {"1mo", "6mo", "1y", "2y", "5y"} else PORTFOLIO_DEFAULTS["lookback"]


def _normalize_objective(value: Any) -> str:
    objective = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    aliases = {
        "sharpe": "max_sharpe",
        "maximum_sharpe": "max_sharpe",
        "max_sharpe": "max_sharpe",
        "minimum_volatility": "min_volatility",
        "minimum_variance": "min_volatility",
        "min_volatility": "min_volatility",
        "min_variance": "min_volatility",
    }
    return aliases.get(objective, PORTFOLIO_DEFAULTS["objective"])


def _normalize_sector(value: Any) -> str:
    sector = str(value or "").strip()
    sector = re.sub(r"\s+(stocks?|sector)$", "", sector, flags=re.IGNORECASE).strip()
    return sector


def _normalize_strategy(value: Any) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return STRATEGY_ALIASES.get(key, key)


def _defaulted_parameters(strategy: str, raw_parameters: Any) -> dict[str, Any]:
    parameters = dict(STRATEGY_DEFAULT_PARAMETERS[strategy])
    if isinstance(raw_parameters, dict):
        parameters.update({key: value for key, value in raw_parameters.items() if value is not None})

    if strategy == "sma_crossover":
        parameters["fast_window"] = parameters.get("fast_window") or parameters.get("fast") or parameters.get("short_window")
        parameters["slow_window"] = parameters.get("slow_window") or parameters.get("slow") or parameters.get("long_window")
        parameters["fast_window"] = _positive_int(parameters.get("fast_window"), 20)
        parameters["slow_window"] = _positive_int(parameters.get("slow_window"), 50)
    elif strategy == "rsi_mean_reversion":
        parameters["rsi_window"] = parameters.get("rsi_window") or parameters.get("window")
        parameters["rsi_window"] = _positive_int(parameters.get("rsi_window"), 14)
        parameters["lower"] = _bounded_float(parameters.get("lower"), 30.0, 0.0, 100.0)
        parameters["upper"] = _bounded_float(parameters.get("upper"), 70.0, 0.0, 100.0)
    elif strategy == "bollinger_reversion":
        parameters["window"] = _positive_int(parameters.get("window"), 20)
        parameters["std_dev"] = parameters.get("std_dev") or parameters.get("std") or parameters.get("standard_deviations")
        parameters["std_dev"] = _positive_float(parameters.get("std_dev"), 2.0)

    return parameters


def _defaulted_monte_carlo(raw_monte_carlo: Any) -> dict[str, Any]:
    monte_carlo = dict(DEFAULTS["monte_carlo"])
    if isinstance(raw_monte_carlo, dict):
        monte_carlo.update({key: value for key, value in raw_monte_carlo.items() if value is not None})

    monte_carlo["enabled"] = bool(monte_carlo.get("enabled", True))
    monte_carlo["days"] = min(_positive_int(monte_carlo.get("days"), 60), 365)
    monte_carlo["simulations"] = min(_positive_int(monte_carlo.get("simulations"), 500), 5000)
    monte_carlo["method"] = "bootstrap"
    return monte_carlo


def _normalize_lookback(value: Any) -> str:
    lookback = str(value or DEFAULTS["lookback"]).strip().lower()
    aliases = {
        "1mo": "1m",
        "1month": "1m",
        "1_month": "1m",
        "6mo": "6m",
        "6month": "6m",
        "6_month": "6m",
        "1yr": "1y",
        "1year": "1y",
        "1_year": "1y",
        "2yr": "2y",
        "2year": "2y",
        "2_year": "2y",
        "5yr": "5y",
        "5year": "5y",
        "5_year": "5y",
    }
    lookback = aliases.get(lookback, lookback)
    return lookback if re.fullmatch(r"\d+[dmy]", lookback) else DEFAULTS["lookback"]


def _looks_like_ticker(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9.]{0,5}", value or ""))


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _bounded_float(value: Any, default: float, lower: float, upper: float) -> float:
    parsed = _positive_float(value, default)
    return parsed if lower < parsed < upper else default


def _bounded_float_inclusive(value: Any, default: float, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if lower <= parsed <= upper else default


def _bounded_int(value: Any, default: int, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if lower <= parsed <= upper else default


def _strategy_label(strategy: str) -> str:
    return {
        "sma_crossover": "SMA Crossover",
        "rsi_mean_reversion": "RSI Mean Reversion",
        "bollinger_reversion": "Bollinger Reversion",
    }.get(strategy, strategy)
