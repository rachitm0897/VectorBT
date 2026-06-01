import json
import re
from functools import lru_cache
from typing import Any, TypedDict

from django.conf import settings
from langgraph.graph import END, StateGraph
from openai import OpenAI, OpenAIError

from apps.agent.cache import load_parsed_request, save_parsed_request
from apps.backtesting.engine import BacktestExecutionError, run_backtest
from apps.backtesting.serializers import BacktestRequestSerializer
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

PARSER_PROMPT = """Return JSON only. Parse a stock backtest request.
Strategies: sma_crossover fast_window=20 slow_window=50; rsi_mean_reversion rsi_window=14 lower=30 upper=70; bollinger_reversion window=20 std_dev=2.
Names: Apple=AAPL Tesla=TSLA Nvidia=NVDA Microsoft=MSFT Amazon=AMZN Meta/Facebook=META Google/Alphabet=GOOGL Netflix=NFLX.
Defaults: strategy=sma_crossover lookback=2y resolution=D initial_cash=10000 fees=0.001 monte_carlo={enabled:true,days:60,simulations:500,method:bootstrap}.
Lookback allowed: 1mo,6mo,1y,2y,5y. Use null when symbol missing.
Output keys: symbol,strategy,parameters,lookback,resolution,initial_cash,fees,monte_carlo."""


class AgentState(TypedDict, total=False):
    message: str
    parsed_request: dict[str, Any]
    validated_request: dict[str, Any]
    backtest_result: dict[str, Any]
    assistant_message: str
    status: str
    warnings: list[str]
    errors: list[str]
    missing_fields: list[str]


def run_chat_workflow(message: str) -> dict[str, Any]:
    state = _graph().invoke({"message": message, "status": "running", "warnings": [], "errors": []})
    return {
        "status": state.get("status", "error"),
        "assistant_message": state.get("assistant_message", "Chat request failed."),
        "parsed_request": state.get("validated_request") or state.get("parsed_request") or {},
        "backtest_result": state.get("backtest_result") or {},
        "warnings": state.get("warnings", []),
        "errors": state.get("errors", []),
        "missing_fields": state.get("missing_fields", []),
    }


def parse_request_node(state: AgentState) -> AgentState:
    cached = load_parsed_request(state["message"])
    if cached is not None:
        return {**state, "parsed_request": cached}

    if not settings.OPENAI_API_KEY:
        return {
            **state,
            "status": "error",
            "errors": ["missing_openai_api_key"],
            "assistant_message": "OPENAI_API_KEY is required to parse new chat requests.",
        }

    try:
        parsed = _call_parser_llm(state["message"])
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

    return {**state, "validated_request": serializer.validated_data, "warnings": warnings}


def run_backtest_node(state: AgentState) -> AgentState:
    if state.get("status") in {"error", "needs_input"}:
        return state

    try:
        result = run_backtest(state["validated_request"])
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


def _call_parser_llm(message: str) -> dict[str, Any]:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        max_tokens=260,
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


def _strategy_label(strategy: str) -> str:
    return {
        "sma_crossover": "SMA Crossover",
        "rsi_mean_reversion": "RSI Mean Reversion",
        "bollinger_reversion": "Bollinger Reversion",
    }.get(strategy, strategy)
