from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.agent.graph import parse_request_node, validate_request_node
from apps.api_keys import api_keys_from_request


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
