import pandas as pd

from django.test import SimpleTestCase
from django.test import override_settings
from unittest.mock import patch

from apps.strategies.registry import StrategyValidationError, build_strategy_signals


class MacdStrategyTests(SimpleTestCase):
    def setUp(self):
        self.close = pd.Series(
            [
                100,
                101,
                102,
                103,
                104,
                105,
                104,
                103,
                102,
                101,
                100,
                99,
                100,
                102,
                104,
                106,
                105,
                103,
                101,
                99,
                98,
                100,
                103,
                106,
                108,
                106,
                103,
                100,
                98,
                101,
            ],
            index=pd.date_range("2024-01-01", periods=30, freq="D"),
            dtype=float,
        )

    def test_macd_crossover_builds_entry_exit_signals(self):
        result = build_strategy_signals(
            "macd_crossover",
            self.close,
            {"fast_period": 3, "slow_period": 6, "signal_period": 2},
        )

        self.assertTrue(result.entries.any())
        self.assertTrue(result.exits.any())
        self.assertEqual(
            result.parameters,
            {"fast_period": 3, "slow_period": 6, "signal_period": 2},
        )
        self.assertEqual(set(result.indicators), {"macd", "signal", "histogram"})

    def test_macd_rejects_fast_period_not_below_slow_period(self):
        with self.assertRaisesRegex(StrategyValidationError, "fast_period"):
            build_strategy_signals(
                "macd_crossover",
                self.close,
                {"fast_period": 10, "slow_period": 5, "signal_period": 3},
            )


class StrategyRegistryAPITests(SimpleTestCase):
    @override_settings(MCP_ENABLED=True)
    @patch("apps.strategies.views.search_remote_strategy_registry")
    def test_strategy_registry_returns_visible_imported_strategies_and_counters(self, search_registry):
        search_registry.return_value = {
            "status": "success",
            "count": 2,
            "total_count": 2,
            "summary": {
                "total_strategies": 2,
                "executable_strategies": 1,
                "catalogue_only_strategies": 1,
                "imported_strategies": 1,
                "built_in_strategies": 1,
                "failed_imports": 0,
            },
            "strategies": [
                {
                    "strategy_id": "sma_crossover",
                    "name": "SMA",
                    "source_type": "built_in",
                    "usability_status": "executable",
                    "executable": True,
                },
                {
                    "strategy_id": "imported_ranker",
                    "name": "Imported Ranker",
                    "source_type": "stock_strategy_profilling",
                    "usability_status": "catalogue_only",
                    "executable": False,
                },
            ],
        }

        response = self.client.get("/api/strategies/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["imported_strategies"], 1)
        self.assertEqual(payload["strategies"][1]["usability_status"], "catalogue_only")
        self.assertFalse(payload["strategies"][1]["executable"])
        self.assertEqual(search_registry.call_args.kwargs["limit"], 1000)

    @override_settings(MCP_ENABLED=True)
    @patch("apps.strategies.views.sync_remote_strategy_registry")
    def test_strategy_registry_sync_endpoint(self, sync_registry):
        sync_registry.return_value = {
            "status": "success",
            "import": {"imported_count": 275, "failures": []},
            "summary": {"total_strategies": 281, "failed_imports": 0},
        }

        response = self.client.post("/api/strategies/sync/", data={}, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["import"]["imported_count"], 275)
