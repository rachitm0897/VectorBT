from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.backtesting.mcp_client import (
    discover_remote_research_name,
    run_remote_factor_portfolio,
    run_remote_portfolio_optimization,
)
from apps.backtesting.serializers import FactorPortfolioRequestSerializer, PortfolioOptimizationRequestSerializer


class PortfolioMCPClientTests(SimpleTestCase):
    @override_settings(
        MCP_ALLOWED_TOOLS={
            "run_strategy_research",
            "run_markowitz_optimization",
            "list_stock_universe",
            "list_sectors",
            "list_stocks_by_sector",
            "resolve_symbols_for_sector",
        }
    )
    @patch("apps.backtesting.mcp_client.call_mcp_tool")
    def test_portfolio_optimization_routes_to_markowitz_with_finnhub_key(self, call_mcp_tool):
        call_mcp_tool.return_value = {
            "status": "success",
            "objective": "max_sharpe",
            "symbols": ["AAPL", "MSFT"],
            "weights": {"AAPL": 0.55, "MSFT": 0.45},
            "metrics": {
                "expected_annual_return_pct": 12.3,
                "annual_volatility_pct": 10.2,
                "sharpe_ratio": 1.2,
            },
            "data_quality": {"symbols_requested": 2, "symbols_used": 2},
        }

        run_remote_portfolio_optimization(
            {
                "symbols": ["AAPL", "MSFT"],
                "lookback": "2y",
                "resolution": "D",
                "objective": "max_sharpe",
                "risk_free_rate": 0.0,
                "allow_short": False,
                "max_weight": 0.6,
                "num_frontier_portfolios": 3000,
                "monte_carlo": {
                    "enabled": True,
                    "days": 60,
                    "simulations": 500,
                    "block_size": 5,
                    "seed": 42,
                    "scenarios": ["neutral", "bullish", "bearish", "crash"],
                    "scenario_overrides": {
                        "bullish": {
                            "drift_shift_annual": 0.1,
                            "volatility_multiplier": 0.8,
                            "initial_shock_pct": 0.0,
                        }
                    },
                },
            },
            finnhub_api_key="user-finnhub-key",
        )

        tool_name, arguments = call_mcp_tool.call_args.args
        self.assertEqual(tool_name, "run_markowitz_optimization")
        self.assertEqual(arguments["finnhub_api_key"], "user-finnhub-key")
        self.assertIsNone(arguments["sector"])
        self.assertTrue(arguments["run_monte_carlo"])
        self.assertEqual(arguments["monte_carlo_days"], 60)
        self.assertEqual(arguments["monte_carlo_simulations"], 500)
        self.assertEqual(arguments["monte_carlo_block_size"], 5)
        self.assertEqual(arguments["monte_carlo_seed"], 42)
        self.assertEqual(arguments["monte_carlo_scenarios"], ["neutral", "bullish", "bearish", "crash"])
        self.assertEqual(arguments["scenario_overrides"]["bullish"]["drift_shift_annual"], 0.1)
        self.assertNotIn("chat_api_key", arguments)
        self.assertNotIn("openai_api_key", arguments)
        self.assertNotIn("model", arguments)
        self.assertNotIn("chat_url", arguments)

    @override_settings(
        MCP_ALLOWED_TOOLS={
            "run_strategy_research",
            "run_markowitz_optimization",
            "list_stock_universe",
            "list_sectors",
            "list_stocks_by_sector",
            "resolve_symbols_for_sector",
        }
    )
    @patch("apps.backtesting.mcp_client.call_mcp_tool")
    def test_portfolio_optimization_routes_sector_to_markowitz(self, call_mcp_tool):
        call_mcp_tool.return_value = {
            "status": "success",
            "objective": "max_sharpe",
            "symbols": ["AAPL", "MSFT", "NVDA"],
            "selection_mode": "sector",
            "sector": "Technology",
            "symbols_used": ["AAPL", "MSFT", "NVDA"],
            "weights": {"AAPL": 0.4, "MSFT": 0.3, "NVDA": 0.3},
            "metrics": {
                "expected_annual_return_pct": 12.3,
                "annual_volatility_pct": 10.2,
                "sharpe_ratio": 1.2,
            },
            "data_quality": {"symbols_requested": 3, "symbols_used": 3},
        }

        response = run_remote_portfolio_optimization(
            {
                "symbols": [],
                "sector": "Technology",
                "lookback": "2y",
                "resolution": "D",
                "objective": "max_sharpe",
                "risk_free_rate": 0.0,
                "allow_short": False,
                "max_weight": 0.6,
                "num_frontier_portfolios": 3000,
            },
            finnhub_api_key="user-finnhub-key",
        )

        tool_name, arguments = call_mcp_tool.call_args.args
        self.assertEqual(tool_name, "run_markowitz_optimization")
        self.assertEqual(arguments["symbols"], [])
        self.assertEqual(arguments["sector"], "Technology")
        self.assertEqual(arguments["finnhub_api_key"], "user-finnhub-key")
        self.assertNotIn("chat_api_key", arguments)
        self.assertNotIn("openai_api_key", arguments)
        self.assertEqual(response["parsed_request"]["sector"], "Technology")
        self.assertEqual(response["portfolio_result"]["selection_mode"], "sector")
        self.assertEqual(response["portfolio_result"]["symbols_used"], ["AAPL", "MSFT", "NVDA"])

    def test_portfolio_serializer_rejects_invalid_scenario(self):
        serializer = PortfolioOptimizationRequestSerializer(
            data={
                "symbols": ["AAPL", "MSFT"],
                "objective": "max_sharpe",
                "monte_carlo": {
                    "enabled": True,
                    "scenarios": ["neutral", "recession"],
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("invalid_scenario", str(serializer.errors))

    @override_settings(
        MCP_ALLOWED_TOOLS={
            "run_strategy_research",
            "run_markowitz_optimization",
            "list_stock_universe",
            "list_sectors",
            "list_stocks_by_sector",
            "resolve_symbols_for_sector",
        }
    )
    @patch("apps.backtesting.mcp_client.call_mcp_tool")
    def test_compact_scenario_result_is_preserved_when_artifact_loading_fails(self, call_mcp_tool):
        call_mcp_tool.return_value = {
            "status": "success",
            "objective": "max_sharpe",
            "symbols": ["AAPL", "MSFT"],
            "weights": {"AAPL": 0.55, "MSFT": 0.45},
            "metrics": {
                "expected_annual_return_pct": 12.3,
                "annual_volatility_pct": 10.2,
                "sharpe_ratio": 1.2,
            },
            "scenario_analysis": {
                "enabled": True,
                "days": 60,
                "simulations": 500,
                "block_size": 5,
                "seed": 42,
                "portfolio_start_value": 10000,
                "scenarios": [
                    {
                        "name": "neutral",
                        "label": "Neutral",
                        "assumptions": {
                            "drift_shift_annual": 0.0,
                            "volatility_multiplier": 1.0,
                            "initial_shock_pct": 0.0,
                        },
                        "summary": {
                            "expected_return_pct": 3.2,
                            "probability_positive_return_pct": 61.0,
                            "probability_loss_above_10_pct": 8.4,
                            "p5_return_pct": -11.2,
                            "p50_return_pct": 2.7,
                            "p95_return_pct": 18.3,
                            "expected_final_value": 10320,
                            "average_max_drawdown_pct": 7.8,
                            "worst_simulated_drawdown_pct": 24.1,
                        },
                    }
                ],
            },
            "artifact_path": "mcp/cache/results/missing.json",
            "data_quality": {"symbols_requested": 2, "symbols_used": 2},
        }

        response = run_remote_portfolio_optimization(
            {
                "symbols": ["AAPL", "MSFT"],
                "lookback": "2y",
                "resolution": "D",
                "objective": "max_sharpe",
                "risk_free_rate": 0.0,
                "allow_short": False,
                "max_weight": 0.6,
                "num_frontier_portfolios": 3000,
                "monte_carlo": {"enabled": True},
            },
            finnhub_api_key="user-finnhub-key",
        )

        result = response["portfolio_result"]
        self.assertEqual(result["weights"], {"AAPL": 0.55, "MSFT": 0.45})
        self.assertTrue(result["scenario_analysis"]["enabled"])
        self.assertEqual(result["scenario_analysis"]["scenarios"][0]["name"], "neutral")
        self.assertIn("Remote MCP artifact was not accessible from backend.", result["warnings"])


class MCPDiscoveryTests(SimpleTestCase):
    @patch("apps.backtesting.mcp_client.call_mcp_tool")
    def test_beta_is_discovered_as_indicator_after_strategy_lookup(self, call_mcp_tool):
        call_mcp_tool.side_effect = [
            {
                "status": "success",
                "strategies": [
                    {"name": "sma_crossover"},
                    {"name": "rsi_mean_reversion"},
                ],
            },
            {
                "status": "success",
                "indicator": "BETA",
                "info": {
                    "name": "BETA",
                    "group": "Statistic Functions",
                    "parameters": {"timeperiod": 5},
                },
            },
        ]

        result = discover_remote_research_name("beta")

        self.assertEqual(result["kind"], "indicator")
        self.assertEqual(result["name"], "BETA")
        self.assertEqual(
            [call.args for call in call_mcp_tool.call_args_list],
            [
                ("list_strategies", {}),
                ("get_indicator_info", {"indicator": "BETA"}),
            ],
        )

    @patch("apps.backtesting.mcp_client.call_mcp_tool")
    def test_supported_strategy_stops_after_strategy_lookup(self, call_mcp_tool):
        call_mcp_tool.return_value = {
            "status": "success",
            "strategies": [{"name": "sma_crossover"}],
        }

        result = discover_remote_research_name("sma_crossover")

        self.assertEqual(result["kind"], "strategy")
        call_mcp_tool.assert_called_once_with("list_strategies", {})


class FactorPortfolioMCPClientTests(SimpleTestCase):
    @override_settings(MCP_ALLOWED_TOOLS={"construct_factor_portfolio"})
    @patch("apps.backtesting.mcp_client.call_mcp_tool")
    def test_factor_portfolio_routes_to_mcp_without_chat_key(self, call_mcp_tool):
        call_mcp_tool.return_value = {
            "status": "success",
            "run_id": "factor_test",
            "factor_scores": [],
            "selected_stocks": [],
            "rejected_stocks": [],
            "optimization_result": {"metrics": {}},
            "portfolio_weights": {},
        }

        run_remote_factor_portfolio(
            {
                "symbols": ["AAPL", "MSFT"],
                "selection_mode": "symbols",
                "lookback": "2y",
                "resolution": "D",
                "factor_model": {
                    "weights": {
                        "fundamental_quality": 0.3,
                        "valuation": 0.2,
                        "momentum": 0.2,
                        "analyst": 0.15,
                        "financial_risk": 0.15,
                    }
                },
                "optimization": {"objective": "max_sharpe"},
                "score_tilt": {"enabled": False},
                "monte_carlo": {"enabled": True},
            },
            finnhub_api_key="finnhub-key",
        )

        tool_name, arguments = call_mcp_tool.call_args.args
        self.assertEqual(tool_name, "construct_factor_portfolio")
        self.assertEqual(arguments["finnhub_api_key"], "finnhub-key")
        self.assertNotIn("chat_api_key", arguments)
        self.assertNotIn("openai_api_key", arguments)
        self.assertNotIn("model", arguments)

    def test_factor_serializer_rejects_invalid_weights(self):
        serializer = FactorPortfolioRequestSerializer(
            data={
                "symbols": ["AAPL", "MSFT"],
                "factor_model": {
                    "weights": {
                        "fundamental_quality": 0.8,
                        "valuation": 0.2,
                        "momentum": 0.2,
                        "analyst": 0.15,
                        "financial_risk": 0.15,
                    }
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("invalid_factor_weights", str(serializer.errors))
