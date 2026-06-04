from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.backtesting.mcp_client import run_remote_portfolio_optimization


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
            },
            finnhub_api_key="user-finnhub-key",
        )

        tool_name, arguments = call_mcp_tool.call_args.args
        self.assertEqual(tool_name, "run_markowitz_optimization")
        self.assertEqual(arguments["finnhub_api_key"], "user-finnhub-key")
        self.assertIsNone(arguments["sector"])
        self.assertNotIn("chat_api_key", arguments)
        self.assertNotIn("openai_api_key", arguments)

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
