from django.test import SimpleTestCase

from apps.seeding.research_seed import (
    SELECTED_SYMBOLS,
    generate_seed_plan,
    make_backtest_run_id,
    make_markowitz_run_id,
)


class ResearchSeedPlanTests(SimpleTestCase):
    def test_full_plan_generates_expected_job_counts(self):
        plan = generate_seed_plan(available_symbols=set(SELECTED_SYMBOLS))

        self.assertEqual(plan.backtest_count, 810)
        self.assertEqual(plan.markowitz_count, 96)
        self.assertEqual(plan.total_count, 906)
        self.assertEqual(plan.missing_symbols, ())

    def test_backtest_run_id_is_stable_and_parameter_sensitive(self):
        first = make_backtest_run_id(
            symbol="AAPL",
            strategy="sma_crossover",
            parameter_slug="10_30",
            parameters={"fast_window": 10, "slow_window": 30},
            lookback="1y",
        )
        second = make_backtest_run_id(
            symbol="AAPL",
            strategy="sma_crossover",
            parameter_slug="10_30",
            parameters={"fast_window": 10, "slow_window": 30},
            lookback="1y",
        )
        different = make_backtest_run_id(
            symbol="AAPL",
            strategy="sma_crossover",
            parameter_slug="20_50",
            parameters={"fast_window": 20, "slow_window": 50},
            lookback="1y",
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_markowitz_run_id_is_stable_and_constraint_sensitive(self):
        symbols = ("AAPL", "MSFT", "NVDA")
        first = make_markowitz_run_id(
            portfolio_name="Mega Tech",
            symbols=symbols,
            objective="max_sharpe",
            lookback="2y",
            max_weight=0.3,
            risk_free_rate=0.0,
            allow_short=False,
            num_frontier_portfolios=3000,
        )
        second = make_markowitz_run_id(
            portfolio_name="Mega Tech",
            symbols=symbols,
            objective="max_sharpe",
            lookback="2y",
            max_weight=0.3,
            risk_free_rate=0.0,
            allow_short=False,
            num_frontier_portfolios=3000,
        )
        different = make_markowitz_run_id(
            portfolio_name="Mega Tech",
            symbols=symbols,
            objective="max_sharpe",
            lookback="2y",
            max_weight=0.5,
            risk_free_rate=0.0,
            allow_short=False,
            num_frontier_portfolios=3000,
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
