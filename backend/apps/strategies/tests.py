import pandas as pd

from django.test import SimpleTestCase

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
