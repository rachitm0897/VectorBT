from __future__ import annotations

import os
import re
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services import analytics_status, get_analytics_connection
from apps.backtesting.engine import (
    BacktestExecutionError,
    run_structured_backtest,
    run_structured_portfolio_optimization,
)
from apps.seeding.research_seed import SeedJob, generate_seed_plan, load_universe_symbols

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - exercised only when tqdm is not installed
    tqdm = None


ANALYTICS_SOURCE = "seed_full_research_data"
RETRY_DELAYS_SECONDS = (2.0, 5.0)
SENSITIVE_MARKERS = ("api_key", "apikey", "authorization", "password", "secret", "token")
TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "temporar",
    "connection",
    "connect",
    "network",
    "503",
    "502",
    "504",
    "server disconnected",
    "mcp server",
    "mcp_tool_error",
)
VALIDATION_MARKERS = (
    "invalid",
    "validation",
    "unsupported",
    "missing_finnhub_api_key",
    "missing_symbols",
    "missing_symbols_or_sector",
    "empty_sector",
    "at least",
    "must be",
    "too low",
    "no stocks found",
    "not enough",
    "no overlapping",
    "no candles",
    "insufficient",
)


class Command(BaseCommand):
    help = "Run the full real research data seed through backend, MCP, and analytics persistence."

    def add_arguments(self, parser):
        parser.add_argument("--finnhub-api-key", dest="finnhub_api_key", default=None)
        parser.add_argument("--force", action="store_true", help="Rerun jobs even when a successful analytics row exists.")
        parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep after executed jobs.")
        parser.add_argument("--max-runs", type=int, default=0, help="Limit executed/planned jobs; 0 means all jobs.")
        parser.add_argument("--skip-markowitz", action="store_true", help="Skip Markowitz optimization jobs.")
        parser.add_argument("--skip-backtests", action="store_true", help="Skip strategy backtest jobs.")
        parser.add_argument("--dry-run", action="store_true", help="Print the plan without executing jobs.")
        parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero if any job fails.")

    def handle(self, *args, **options):
        sleep_seconds = float(options["sleep"])
        max_runs = int(options["max_runs"] or 0)
        dry_run = bool(options["dry_run"])
        force = bool(options["force"])

        if sleep_seconds < 0:
            raise CommandError("--sleep must be greater than or equal to 0.")
        if max_runs < 0:
            raise CommandError("--max-runs must be greater than or equal to 0.")

        finnhub_api_key = options.get("finnhub_api_key") or os.getenv("FINNHUB_API_KEY")
        if not dry_run and not finnhub_api_key:
            raise CommandError("Finnhub API key is required. Pass --finnhub-api-key or set FINNHUB_API_KEY.")

        universe_symbols, universe_path, attempted_paths = load_universe_symbols()
        if universe_path:
            self.stdout.write(f"Loaded stock universe: {universe_path}")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Local universe file was not found; using the fixed 30-stock seed list without filtering."
                )
            )
            self.stdout.write(f"Universe paths checked: {', '.join(str(path) for path in attempted_paths)}")

        plan = generate_seed_plan(
            available_symbols=universe_symbols,
            include_backtests=not bool(options["skip_backtests"]),
            include_markowitz=not bool(options["skip_markowitz"]),
        )
        for symbol in plan.missing_symbols:
            self.stdout.write(self.style.WARNING(f"Selected ticker missing from universe; skipping {symbol}."))
        for portfolio_name in plan.skipped_portfolios:
            self.stdout.write(
                self.style.WARNING(
                    f"Portfolio has fewer than two available symbols; skipping {portfolio_name}."
                )
            )

        all_jobs = plan.jobs
        jobs = all_jobs[:max_runs] if max_runs else all_jobs

        self.stdout.write("")
        self.stdout.write("Full research seed plan")
        self.stdout.write(f"Backtest jobs: {plan.backtest_count}")
        self.stdout.write(f"Markowitz jobs: {plan.markowitz_count}")
        self.stdout.write(f"Total jobs: {plan.total_count}")
        if max_runs:
            self.stdout.write(f"Planned jobs this run: {len(jobs)} (--max-runs {max_runs})")
        else:
            self.stdout.write(f"Planned jobs this run: {len(jobs)}")

        if dry_run:
            self._print_dry_run_jobs(jobs)
            self.stdout.write("")
            self.stdout.write("Dry run completed. No jobs were executed.")
            return

        self._ensure_analytics_ready()
        if not jobs:
            self.stdout.write("No jobs selected.")
            return

        started = time.perf_counter()
        success_count = 0
        skipped_count = 0
        failed_count = 0
        failed_jobs: list[tuple[SeedJob, str]] = []
        progress = self._progress_bar(total=len(jobs))

        try:
            for index, job in enumerate(jobs, start=1):
                if not force and self._successful_run_exists(job):
                    skipped_count += 1
                    self._write_job_line(
                        progress,
                        index,
                        len(jobs),
                        job,
                        "SKIPPED",
                        reason="already_exists",
                        totals=(success_count, skipped_count, failed_count),
                    )
                    self._advance_progress(progress, success_count, skipped_count, failed_count)
                    continue

                self._write_job_line(progress, index, len(jobs), job, "RUNNING")
                job_started = time.perf_counter()
                executed = False
                try:
                    self._run_with_retries(progress, index, len(jobs), job, finnhub_api_key)
                    executed = True
                    success_count += 1
                    runtime = time.perf_counter() - job_started
                    self._write_job_line(
                        progress,
                        index,
                        len(jobs),
                        job,
                        "SUCCESS",
                        runtime=runtime,
                        totals=(success_count, skipped_count, failed_count),
                    )
                    if not self._successful_run_exists(job):
                        self._write(
                            progress,
                            self.style.WARNING(
                                f"[{index:03d}/{len(jobs)}] {job.kind.upper()} WARNING  "
                                f"{job.description} persistence_check=missing_success_row"
                            ),
                        )
                except Exception as exc:
                    failed_count += 1
                    runtime = time.perf_counter() - job_started
                    message = _safe_error(exc)
                    failed_jobs.append((job, message))
                    self._write_job_line(
                        progress,
                        index,
                        len(jobs),
                        job,
                        "FAILED",
                        runtime=runtime,
                        reason=message,
                        totals=(success_count, skipped_count, failed_count),
                    )
                finally:
                    self._advance_progress(progress, success_count, skipped_count, failed_count)

                if executed and sleep_seconds > 0 and index < len(jobs):
                    time.sleep(sleep_seconds)
        finally:
            if progress is not None:
                progress.close()

        runtime = time.perf_counter() - started
        self.stdout.write("")
        self.stdout.write("Full research seed completed.")
        self.stdout.write("")
        self.stdout.write(f"Total jobs: {len(jobs)}")
        self.stdout.write(f"Succeeded: {success_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Failed: {failed_count}")
        self.stdout.write(f"Runtime: {_format_duration(runtime)}")

        if failed_jobs:
            self.stdout.write("")
            self.stdout.write("Failed jobs:")
            for job, message in failed_jobs:
                self.stdout.write(f"- {job.description}: {message}")

        if failed_jobs and options["fail_on_error"]:
            raise CommandError(f"{len(failed_jobs)} seed job(s) failed.")

    def _print_dry_run_jobs(self, jobs: list[SeedJob]) -> None:
        if not jobs:
            return
        self.stdout.write("")
        self.stdout.write("Planned jobs:")
        total = len(jobs)
        for index, job in enumerate(jobs, start=1):
            self.stdout.write(f"[{index:03d}/{total}] {job.kind.upper()} DRY_RUN  {job.description}")

    def _ensure_analytics_ready(self) -> None:
        if not getattr(settings, "MCP_ENABLED", False):
            raise CommandError("MCP is disabled. Set MCP_ENABLED=true before running the full research seed.")

        status = analytics_status()
        if not status.get("enabled"):
            raise CommandError("Analytics persistence is disabled. Set ANALYTICS_ENABLED=true.")
        if not status.get("connected"):
            message = status.get("error") or "Analytics database is not reachable."
            raise CommandError(f"Analytics persistence is not connected: {message}")

    def _successful_run_exists(self, job: SeedJob) -> bool:
        with get_analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT 1 FROM {job.table_name} WHERE run_id = %s AND LOWER(status) = 'success' LIMIT 1",
                    (job.run_id,),
                )
                return cursor.fetchone() is not None

    def _run_with_retries(
        self,
        progress: Any,
        index: int,
        total: int,
        job: SeedJob,
        finnhub_api_key: str,
    ) -> None:
        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            try:
                self._execute_job(job, finnhub_api_key)
                return
            except Exception as exc:
                if attempt >= len(RETRY_DELAYS_SECONDS) or not _is_retryable(exc):
                    raise
                delay = RETRY_DELAYS_SECONDS[attempt]
                self._write(
                    progress,
                    f"[{index:03d}/{total}] {job.kind.upper()} RETRY  "
                    f"{job.description} attempt={attempt + 1} reason={_safe_error(exc)} "
                    f"next_retry={delay:g}s",
                )
                time.sleep(delay)

    def _execute_job(self, job: SeedJob, finnhub_api_key: str) -> None:
        if job.kind == "backtest":
            run_structured_backtest(
                job.payload,
                finnhub_api_key=finnhub_api_key,
                analytics_source=ANALYTICS_SOURCE,
            )
            return

        run_structured_portfolio_optimization(
            job.payload,
            finnhub_api_key=finnhub_api_key,
            analytics_source=ANALYTICS_SOURCE,
        )

    def _write_job_line(
        self,
        progress: Any,
        index: int,
        total: int,
        job: SeedJob,
        status: str,
        *,
        runtime: float | None = None,
        reason: str | None = None,
        totals: tuple[int, int, int] | None = None,
    ) -> None:
        fragments = [f"[{index:03d}/{total}] {job.kind.upper()} {status:<7} {job.description}"]
        if runtime is not None:
            fragments.append(f"runtime={runtime:.2f}s")
        if reason:
            label = "reason" if status == "SKIPPED" else "error"
            fragments.append(f"{label}={reason}")
        if totals:
            success_count, skipped_count, failed_count = totals
            fragments.append(
                f"totals=success:{success_count} skipped:{skipped_count} failed:{failed_count}"
            )
        self._write(progress, "  ".join(fragments))

    def _progress_bar(self, total: int):
        if tqdm is None:
            return None
        return tqdm(total=total, unit="job", dynamic_ncols=True)

    def _advance_progress(
        self,
        progress: Any,
        success_count: int,
        skipped_count: int,
        failed_count: int,
    ) -> None:
        if progress is None:
            return
        progress.set_postfix(success=success_count, skipped=skipped_count, failed=failed_count)
        progress.update(1)

    def _write(self, progress: Any, message: str) -> None:
        if progress is not None:
            progress.write(str(message))
        else:
            self.stdout.write(str(message))


def _is_retryable(exc: Exception) -> bool:
    text = f"{getattr(exc, 'code', '')} {exc}".lower()
    if any(marker in text for marker in VALIDATION_MARKERS):
        return False
    if any(marker in text for marker in TRANSIENT_MARKERS):
        return True
    if isinstance(exc, BacktestExecutionError):
        return "mcp" in str(getattr(exc, "code", "")).lower()
    return False


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    for marker in SENSITIVE_MARKERS:
        message = re.sub(
            rf"({marker}\s*[=:]\s*)[^\s,;]+",
            rf"\1[REDACTED]",
            message,
            flags=re.IGNORECASE,
        )
    return message[:500]


def _format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
