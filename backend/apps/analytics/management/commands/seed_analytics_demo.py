from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services import get_analytics_connection
from apps.analytics.sql import SCHEMA_STATEMENTS

try:
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover - dependency is installed in the backend image.
    Json = None


SAMPLES = [
    {
        "run_id": "demo_aapl_sma_crossover",
        "symbol": "AAPL",
        "strategy": "sma_crossover",
        "lookback": "2y",
        "parameters": {"fast_window": 20, "slow_window": 50},
        "metrics": {
            "total_return_pct": 18.4,
            "buy_hold_return_pct": 15.2,
            "alpha_vs_buy_hold_pct": 3.2,
            "sharpe_ratio": 1.18,
            "max_drawdown_pct": 10.6,
            "win_rate_pct": 54.2,
            "total_trades": 14,
            "final_value": 11840.0,
        },
        "summary": {
            "monte_carlo_expected_return_pct": 4.9,
            "probability_positive_return_pct": 67.5,
            "p5_return_pct": -5.8,
            "p95_return_pct": 13.9,
        },
        "diagnostics": {"llm_calls": 0, "parser_cache": "N/A", "cache_status": "HIT", "candles_fetched": 505},
        "trades": [(0, 45, 186.2, 194.8, 462.0, 4.62), (88, 126, 189.1, 181.4, -407.0, -4.07), (180, 241, 171.6, 189.9, 982.0, 9.82)],
        "equity": [10000.0, 10380.0, 9920.0, 11150.0, 11840.0],
    },
    {
        "run_id": "demo_aapl_rsi_mean_reversion",
        "symbol": "AAPL",
        "strategy": "rsi_mean_reversion",
        "lookback": "2y",
        "parameters": {"rsi_window": 14, "lower": 30, "upper": 70},
        "metrics": {
            "total_return_pct": 11.7,
            "buy_hold_return_pct": 15.2,
            "alpha_vs_buy_hold_pct": -3.5,
            "sharpe_ratio": 0.92,
            "max_drawdown_pct": 8.9,
            "win_rate_pct": 59.1,
            "total_trades": 22,
            "final_value": 11170.0,
        },
        "summary": {
            "monte_carlo_expected_return_pct": 3.1,
            "probability_positive_return_pct": 61.2,
            "p5_return_pct": -4.2,
            "p95_return_pct": 10.4,
        },
        "diagnostics": {"llm_calls": 1, "parser_cache": "MISS", "cache_status": "HIT", "candles_fetched": 505},
        "trades": [(8, 17, 182.4, 187.8, 296.0, 2.96), (72, 79, 195.2, 192.6, -142.0, -1.42), (156, 169, 174.1, 181.3, 394.0, 3.94)],
        "equity": [10000.0, 10190.0, 10410.0, 10740.0, 11170.0],
    },
    {
        "run_id": "demo_nvda_sma_crossover",
        "symbol": "NVDA",
        "strategy": "sma_crossover",
        "lookback": "2y",
        "parameters": {"fast_window": 20, "slow_window": 50},
        "metrics": {
            "total_return_pct": 42.8,
            "buy_hold_return_pct": 55.6,
            "alpha_vs_buy_hold_pct": -12.8,
            "sharpe_ratio": 1.36,
            "max_drawdown_pct": 18.7,
            "win_rate_pct": 51.4,
            "total_trades": 18,
            "final_value": 14280.0,
        },
        "summary": {
            "monte_carlo_expected_return_pct": 7.4,
            "probability_positive_return_pct": 70.3,
            "p5_return_pct": -9.1,
            "p95_return_pct": 24.5,
        },
        "diagnostics": {"llm_calls": 0, "parser_cache": "N/A", "cache_status": "MISS", "candles_fetched": 505},
        "trades": [(4, 64, 89.5, 105.4, 1776.0, 17.76), (111, 142, 118.3, 113.6, -526.0, -5.26), (205, 283, 122.2, 151.8, 3318.0, 33.18)],
        "equity": [10000.0, 11580.0, 10960.0, 13020.0, 14280.0],
    },
    {
        "run_id": "demo_nvda_bollinger_reversion",
        "symbol": "NVDA",
        "strategy": "bollinger_reversion",
        "lookback": "2y",
        "parameters": {"window": 20, "std_dev": 2},
        "metrics": {
            "total_return_pct": 29.5,
            "buy_hold_return_pct": 55.6,
            "alpha_vs_buy_hold_pct": -26.1,
            "sharpe_ratio": 1.08,
            "max_drawdown_pct": 14.9,
            "win_rate_pct": 62.0,
            "total_trades": 25,
            "final_value": 12950.0,
        },
        "summary": {
            "monte_carlo_expected_return_pct": 5.6,
            "probability_positive_return_pct": 65.9,
            "p5_return_pct": -7.6,
            "p95_return_pct": 18.8,
        },
        "diagnostics": {"llm_calls": 1, "parser_cache": "HIT", "cache_status": "HIT", "candles_fetched": 505},
        "trades": [(13, 24, 96.7, 101.4, 486.0, 4.86), (97, 106, 115.0, 121.5, 673.0, 6.73), (188, 202, 135.6, 128.2, -765.0, -7.65)],
        "equity": [10000.0, 10640.0, 11620.0, 12190.0, 12950.0],
    },
    {
        "run_id": "demo_tsla_rsi_mean_reversion",
        "symbol": "TSLA",
        "strategy": "rsi_mean_reversion",
        "lookback": "2y",
        "parameters": {"rsi_window": 14, "lower": 28, "upper": 72},
        "metrics": {
            "total_return_pct": -6.8,
            "buy_hold_return_pct": -2.1,
            "alpha_vs_buy_hold_pct": -4.7,
            "sharpe_ratio": -0.22,
            "max_drawdown_pct": 24.6,
            "win_rate_pct": 45.8,
            "total_trades": 24,
            "final_value": 9320.0,
        },
        "summary": {
            "monte_carlo_expected_return_pct": -1.4,
            "probability_positive_return_pct": 43.8,
            "p5_return_pct": -17.8,
            "p95_return_pct": 16.2,
        },
        "diagnostics": {"llm_calls": 1, "parser_cache": "MISS", "cache_status": "MISS", "candles_fetched": 505},
        "trades": [(2, 11, 214.2, 207.5, -312.0, -3.12), (69, 77, 178.4, 184.9, 303.0, 3.03), (145, 157, 194.6, 181.1, -629.0, -6.29)],
        "equity": [10000.0, 9680.0, 10110.0, 9040.0, 9320.0],
    },
    {
        "run_id": "demo_msft_sma_crossover",
        "symbol": "MSFT",
        "strategy": "sma_crossover",
        "lookback": "2y",
        "parameters": {"fast_window": 30, "slow_window": 90},
        "metrics": {
            "total_return_pct": 21.9,
            "buy_hold_return_pct": 19.4,
            "alpha_vs_buy_hold_pct": 2.5,
            "sharpe_ratio": 1.31,
            "max_drawdown_pct": 9.3,
            "win_rate_pct": 56.7,
            "total_trades": 12,
            "final_value": 12190.0,
        },
        "summary": {
            "monte_carlo_expected_return_pct": 4.2,
            "probability_positive_return_pct": 66.1,
            "p5_return_pct": -3.9,
            "p95_return_pct": 12.6,
        },
        "diagnostics": {"llm_calls": 0, "parser_cache": "N/A", "cache_status": "HIT", "candles_fetched": 505},
        "trades": [(7, 49, 410.4, 426.7, 397.0, 3.97), (117, 152, 438.2, 431.8, -156.0, -1.56), (213, 277, 421.3, 452.6, 762.0, 7.62)],
        "equity": [10000.0, 10460.0, 10890.0, 11610.0, 12190.0],
    },
]


class Command(BaseCommand):
    help = "Seed analytics PostgreSQL tables with demo backtest rows."

    def handle(self, *args, **options):
        if Json is None:
            raise CommandError("psycopg is not installed. Install backend requirements before seeding analytics.")

        try:
            with get_analytics_connection() as connection:
                with connection.cursor() as cursor:
                    for statement in SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                    for offset, sample in enumerate(SAMPLES):
                        self._seed_sample(cursor, sample, offset)
        except Exception as exc:
            raise CommandError(f"Could not seed analytics demo data: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(SAMPLES)} analytics demo runs."))

    def _seed_sample(self, cursor, sample: dict, offset: int) -> None:
        created_at = datetime.utcnow() - timedelta(days=(len(SAMPLES) - offset) * 3)
        request_json = {
            "symbol": sample["symbol"],
            "strategy": sample["strategy"],
            "lookback": sample["lookback"],
            "resolution": "D",
            "initial_cash": 10000,
            "fees": 0.001,
            "parameters": sample["parameters"],
            "monte_carlo": {"enabled": True, "days": 60, "simulations": 500, "method": "bootstrap"},
        }
        metrics = sample["metrics"]
        summary = sample["summary"]
        diagnostics = sample["diagnostics"]

        cursor.execute(
            """
            INSERT INTO backtest_runs (
                run_id, created_at, source, status, symbol, strategy, lookback, resolution,
                initial_cash, fees, total_return_pct, buy_hold_return_pct, alpha_vs_buy_hold_pct,
                sharpe_ratio, max_drawdown_pct, win_rate_pct, total_trades, final_value,
                monte_carlo_days, monte_carlo_simulations, mc_expected_return_pct,
                mc_probability_positive_pct, mc_p5_return_pct, mc_p95_return_pct, llm_calls,
                parser_cache, cache_status, candles_fetched, request_json, metrics_json,
                summary_json, diagnostics_json
            )
            VALUES (
                %s, %s, 'demo_seed', 'success', %s, %s, %s, 'D', 10000, 0.001,
                %s, %s, %s, %s, %s, %s, %s, %s, 60, 500, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (run_id) DO UPDATE SET
                created_at = EXCLUDED.created_at,
                source = EXCLUDED.source,
                status = EXCLUDED.status,
                symbol = EXCLUDED.symbol,
                strategy = EXCLUDED.strategy,
                lookback = EXCLUDED.lookback,
                resolution = EXCLUDED.resolution,
                initial_cash = EXCLUDED.initial_cash,
                fees = EXCLUDED.fees,
                total_return_pct = EXCLUDED.total_return_pct,
                buy_hold_return_pct = EXCLUDED.buy_hold_return_pct,
                alpha_vs_buy_hold_pct = EXCLUDED.alpha_vs_buy_hold_pct,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                win_rate_pct = EXCLUDED.win_rate_pct,
                total_trades = EXCLUDED.total_trades,
                final_value = EXCLUDED.final_value,
                monte_carlo_days = EXCLUDED.monte_carlo_days,
                monte_carlo_simulations = EXCLUDED.monte_carlo_simulations,
                mc_expected_return_pct = EXCLUDED.mc_expected_return_pct,
                mc_probability_positive_pct = EXCLUDED.mc_probability_positive_pct,
                mc_p5_return_pct = EXCLUDED.mc_p5_return_pct,
                mc_p95_return_pct = EXCLUDED.mc_p95_return_pct,
                llm_calls = EXCLUDED.llm_calls,
                parser_cache = EXCLUDED.parser_cache,
                cache_status = EXCLUDED.cache_status,
                candles_fetched = EXCLUDED.candles_fetched,
                request_json = EXCLUDED.request_json,
                metrics_json = EXCLUDED.metrics_json,
                summary_json = EXCLUDED.summary_json,
                diagnostics_json = EXCLUDED.diagnostics_json
            """,
            (
                sample["run_id"],
                created_at,
                sample["symbol"],
                sample["strategy"],
                sample["lookback"],
                metrics["total_return_pct"],
                metrics["buy_hold_return_pct"],
                metrics["alpha_vs_buy_hold_pct"],
                metrics["sharpe_ratio"],
                metrics["max_drawdown_pct"],
                metrics["win_rate_pct"],
                metrics["total_trades"],
                metrics["final_value"],
                summary["monte_carlo_expected_return_pct"],
                summary["probability_positive_return_pct"],
                summary["p5_return_pct"],
                summary["p95_return_pct"],
                diagnostics["llm_calls"],
                diagnostics["parser_cache"],
                diagnostics["cache_status"],
                diagnostics["candles_fetched"],
                Json(request_json),
                Json(metrics),
                Json(summary),
                Json(diagnostics),
            ),
        )

        cursor.execute("DELETE FROM backtest_parameters WHERE run_id = %s", (sample["run_id"],))
        for name, value in sample["parameters"].items():
            cursor.execute(
                """
                INSERT INTO backtest_parameters (run_id, parameter_name, parameter_value)
                VALUES (%s, %s, %s)
                """,
                (sample["run_id"], name, str(value)),
            )

        cursor.execute("DELETE FROM backtest_trades WHERE run_id = %s", (sample["run_id"],))
        for trade_index, trade in enumerate(sample["trades"], start=1):
            entry_offset, exit_offset, entry_price, exit_price, pnl, return_pct = trade
            cursor.execute(
                """
                INSERT INTO backtest_trades (
                    run_id, symbol, strategy, entry_time, exit_time, side, entry_price,
                    exit_price, pnl, return_pct, duration_days, status
                )
                VALUES (%s, %s, %s, %s, %s, 'long', %s, %s, %s, %s, %s, 'closed')
                """,
                (
                    sample["run_id"],
                    sample["symbol"],
                    sample["strategy"],
                    created_at + timedelta(days=entry_offset + trade_index),
                    created_at + timedelta(days=exit_offset + trade_index),
                    entry_price,
                    exit_price,
                    pnl,
                    return_pct,
                    exit_offset - entry_offset,
                ),
            )

        cursor.execute("DELETE FROM equity_points WHERE run_id = %s", (sample["run_id"],))
        peak = sample["equity"][0]
        for point_index, value in enumerate(sample["equity"]):
            peak = max(peak, value)
            drawdown_pct = round(((value / peak) - 1) * 100, 4)
            cursor.execute(
                """
                INSERT INTO equity_points (
                    run_id, time, strategy_equity, buy_hold_equity, spy_equity, drawdown_pct
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    sample["run_id"],
                    created_at + timedelta(days=point_index * 45),
                    value,
                    round(value * 0.96, 2),
                    round(10000 * (1 + point_index * 0.025), 2),
                    drawdown_pct,
                ),
            )

