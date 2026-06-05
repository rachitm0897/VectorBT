import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.agent.graph import (
    PARSER_PROMPT,
    _call_parser_llm,
    _runtime_context,
    parse_request_node,
    run_backtest_node,
    run_chat_workflow,
    validate_request_node,
)
from apps.api_keys import api_keys_from_request
from apps.langsmith_tracing import REDACTED, request_id_context, safe_metadata


class RequestConfigTests(SimpleTestCase):
    @override_settings(DEFAULT_CHAT_URL="https://default.example/v1", DEFAULT_CHAT_MODEL="default-model")
    def test_new_chat_config_fields_are_normalized(self):
        request = SimpleNamespace(
            headers={},
            data={
                "chat_url": "https://chat.example/v1",
                "chat_api_key": " user-chat-key ",
                "model": "custom-model",
                "finnhub_api_key": " user-finnhub-key ",
            },
        )

        config = api_keys_from_request(request)

        self.assertEqual(config.chat_url, "https://chat.example/v1")
        self.assertEqual(config.chat_api_key, "user-chat-key")
        self.assertEqual(config.model, "custom-model")
        self.assertEqual(config.finnhub_api_key, "user-finnhub-key")

    @override_settings(DEFAULT_CHAT_URL="https://default.example/v1", DEFAULT_CHAT_MODEL="default-model")
    def test_old_openai_aliases_are_still_supported(self):
        request = SimpleNamespace(
            headers={},
            data={
                "openai_base_url": "https://legacy.example/v1",
                "openai_api_key": "legacy-chat-key",
                "openai_model": "legacy-model",
                "finnhubApiKey": "legacy-finnhub-key",
            },
        )

        config = api_keys_from_request(request)

        self.assertEqual(config.chat_url, "https://legacy.example/v1")
        self.assertEqual(config.chat_api_key, "legacy-chat-key")
        self.assertEqual(config.model, "legacy-model")
        self.assertEqual(config.finnhub_api_key, "legacy-finnhub-key")


class ParserConfigTests(SimpleTestCase):
    def test_missing_chat_api_key_returns_clean_error(self):
        state = parse_request_node({"message": "Backtest AAPL", "chat_api_key": ""})

        self.assertEqual(state["status"], "error")
        self.assertEqual(state["errors"], ["missing_chat_api_key"])
        self.assertEqual(state["assistant_message"], "Chat API key is required for natural language parsing.")

    @patch("apps.agent.graph.save_parsed_request")
    @patch("apps.agent.graph.load_parsed_request", return_value=None)
    @patch("apps.agent.graph._call_parser_llm")
    def test_parser_uses_runtime_chat_url_key_and_model(self, call_parser_llm, _load_cache, _save_cache):
        call_parser_llm.return_value = {
            "request_type": "portfolio_optimization",
            "symbols": [],
            "sector": "Technology",
        }

        parse_request_node(
            {
                "message": "Optimize a Technology sector portfolio using Markowitz.",
                "chat_url": "https://provider.example/v1",
                "chat_api_key": "runtime-chat-key",
                "model": "runtime-model",
            }
        )

        call_parser_llm.assert_called_once_with(
            "Optimize a Technology sector portfolio using Markowitz.",
            api_key="runtime-chat-key",
            chat_url="https://provider.example/v1",
            model="runtime-model",
        )

    def test_sector_markowitz_request_validates_without_symbols(self):
        state = validate_request_node(
            {
                "parsed_request": {
                    "request_type": "portfolio_optimization",
                    "symbols": [],
                    "sector": "Technology",
                    "objective": "max_sharpe",
                },
                "warnings": [],
            }
        )

        self.assertEqual(state["result_type"], "portfolio_optimization")
        self.assertNotEqual(state.get("status"), "needs_input")
        self.assertEqual(state["validated_request"]["symbols"], [])
        self.assertEqual(state["validated_request"]["sector"], "Technology")
        self.assertEqual(state["validated_request"]["objective"], "max_sharpe")

    def test_min_volatility_sector_request_validates_without_symbols(self):
        state = validate_request_node(
            {
                "parsed_request": {
                    "request_type": "portfolio_optimization",
                    "symbols": [],
                    "sector": "Healthcare",
                    "objective": "min_volatility",
                },
                "warnings": [],
            }
        )

        self.assertEqual(state["validated_request"]["symbols"], [])
        self.assertEqual(state["validated_request"]["sector"], "Healthcare")
        self.assertEqual(state["validated_request"]["objective"], "min_volatility")

    @patch("apps.agent.graph._discover_research_name")
    def test_beta_indicator_is_not_silently_replaced_with_sma(self, discover):
        discover.return_value = {
            "kind": "indicator",
            "name": "BETA",
            "strategies": [
                "sma_crossover",
                "rsi_mean_reversion",
                "bollinger_reversion",
            ],
        }

        state = validate_request_node(
            {
                "parsed_request": {
                    "request_type": "strategy_backtest",
                    "symbol": "AAPL",
                    "strategy": "BETA",
                    "parameters": {},
                },
                "warnings": [],
            }
        )

        self.assertEqual(state["status"], "needs_input")
        self.assertEqual(state["errors"], ["indicator_not_strategy"])
        self.assertEqual(state["missing_fields"], ["strategy_rules"])
        self.assertIn("TA-Lib indicator", state["assistant_message"])
        self.assertNotIn("validated_request", state)
        discover.assert_called_once_with("beta")

    @patch("apps.agent.graph._discover_research_name")
    def test_unknown_strategy_returns_supported_strategy_names(self, discover):
        discover.return_value = {
            "kind": "unknown",
            "name": "NOT_REAL",
            "strategies": ["sma_crossover", "rsi_mean_reversion"],
        }

        state = validate_request_node(
            {
                "parsed_request": {
                    "request_type": "strategy_backtest",
                    "symbol": "AAPL",
                    "strategy": "not real",
                },
                "warnings": [],
            }
        )

        self.assertEqual(state["status"], "needs_input")
        self.assertEqual(state["errors"], ["unsupported_strategy"])
        self.assertIn("sma_crossover", state["assistant_message"])
        self.assertNotIn("validated_request", state)

    def test_parser_prompt_preserves_unknown_strategy_names(self):
        self.assertIn("preserve that normalized name", PARSER_PROMPT)
        self.assertIn("Do not silently replace it", PARSER_PROMPT)

    def test_macd_prompt_validates_as_registered_strategy(self):
        state = validate_request_node(
            {
                "parsed_request": {
                    "request_type": "strategy_backtest",
                    "symbol": "AAPL",
                    "strategy": "MACD",
                    "parameters": {},
                },
                "warnings": [],
            }
        )

        self.assertEqual(state["validated_request"]["strategy"], "macd_crossover")
        self.assertEqual(
            state["validated_request"]["parameters"],
            {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        )
        self.assertNotEqual(state.get("status"), "needs_input")

    def test_macd_parameter_aliases_are_normalized(self):
        state = validate_request_node(
            {
                "parsed_request": {
                    "request_type": "strategy_backtest",
                    "symbol": "AAPL",
                    "strategy": "macd_crossover",
                    "parameters": {
                        "fastperiod": 8,
                        "slowperiod": 21,
                        "signalperiod": 5,
                    },
                },
                "warnings": [],
            }
        )

        self.assertEqual(
            state["validated_request"]["parameters"],
            {"fast_period": 8, "slow_period": 21, "signal_period": 5},
        )

    @patch("apps.agent.graph._graph")
    def test_workflow_does_not_put_api_keys_in_langgraph_state(self, graph_factory):
        graph_factory.return_value.invoke.return_value = {
            "status": "success",
            "assistant_message": "Done.",
            "validated_request": {"request_type": "strategy_backtest", "symbol": "AAPL"},
        }

        with patch.dict(
            os.environ,
            {"LANGSMITH_TRACING": "false"},
            clear=False,
        ):
            run_chat_workflow(
                "Backtest AAPL",
                chat_api_key="openai-secret",
                finnhub_api_key="finnhub-secret",
            )

        graph_state = graph_factory.return_value.invoke.call_args.args[0]
        self.assertNotIn("chat_api_key", graph_state)
        self.assertNotIn("finnhub_api_key", graph_state)
        self.assertEqual(graph_state["message"], "Backtest AAPL")
        self.assertTrue(graph_state["request_id"])

    @patch("apps.agent.graph.wrap_openai")
    @patch("apps.agent.graph.OpenAI")
    def test_llm_trace_metadata_contains_model_without_secrets(self, openai_class, wrap_openai):
        raw_client = Mock()
        wrapped_client = Mock()
        wrapped_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"request_type":"strategy_backtest","symbol":"AAPL"}'
                    )
                )
            ]
        )
        openai_class.return_value = raw_client
        wrap_openai.return_value = wrapped_client

        with patch.dict(
            os.environ,
            {
                "LANGSMITH_TRACING": "true",
                "LANGSMITH_API_KEY": "langsmith-test-key",
            },
            clear=False,
        ):
            with request_id_context("request-123"):
                parsed = _call_parser_llm(
                    "Backtest AAPL",
                    api_key="openai-secret",
                    chat_url="https://api.openai.com/v1",
                    model="test-model",
                )

        self.assertEqual(parsed["symbol"], "AAPL")
        openai_class.assert_called_once_with(
            api_key="openai-secret",
            base_url="https://api.openai.com/v1",
        )
        wrap_openai.assert_called_once_with(
            raw_client,
            chat_name="finance_request_parser",
        )
        call_kwargs = wrapped_client.chat.completions.create.call_args.kwargs
        metadata = call_kwargs["langsmith_extra"]["metadata"]
        self.assertEqual(metadata["request_id"], "request-123")
        self.assertEqual(metadata["model"], "test-model")
        self.assertEqual(metadata["messages_count"], 2)
        self.assertNotIn("openai-secret", str(metadata))
        self.assertNotIn("langsmith-test-key", str(metadata))

    @patch("apps.agent.graph.run_backtest")
    def test_graph_state_keeps_compact_backtest_summary(self, run_backtest):
        full_result = {
            "status": "success",
            "request": {"symbol": "AAPL", "strategy": "sma_crossover"},
            "metrics": {"total_return_pct": 12.5, "sharpe_ratio": 1.1},
            "charts": {"price": [{"time": str(index), "close": index} for index in range(500)]},
            "tables": {"trades": [{"id": index} for index in range(100)]},
        }
        run_backtest.return_value = full_result
        result_sink = {}

        with _runtime_context(
            {"chat_api_key": "openai-secret", "finnhub_api_key": "finnhub-secret"},
            result_sink,
        ):
            state = run_backtest_node(
                {
                    "status": "running",
                    "result_type": "strategy_backtest",
                    "validated_request": {
                        "symbol": "AAPL",
                        "strategy": "sma_crossover",
                    },
                    "warnings": [],
                }
            )

        self.assertIs(result_sink["backtest_result"], full_result)
        self.assertEqual(state["backtest_result"]["metrics"]["total_return_pct"], 12.5)
        self.assertNotIn("charts", state["backtest_result"])
        self.assertNotIn("tables", state["backtest_result"])


class LangSmithSafetyTests(SimpleTestCase):
    def test_backend_secret_redaction(self):
        sanitized = safe_metadata(
            {
                "finnhub_api_key": "finnhub-secret",
                "openai_api_key": "openai-secret",
                "password": "password-secret",
            }
        )

        self.assertEqual(sanitized["finnhub_api_key"], REDACTED)
        self.assertEqual(sanitized["openai_api_key"], REDACTED)
        self.assertEqual(sanitized["password"], REDACTED)
