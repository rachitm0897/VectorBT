from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from repositories.base import analytics_connection


class RunRepository:
    def save_research_run(self, envelope: dict[str, Any]) -> dict[str, Any]:
        run_id = envelope.get("run_id")
        if not run_id:
            return {"saved": False, "reason": "missing_run_id"}
        strategy = envelope.get("strategy") if isinstance(envelope.get("strategy"), dict) else {}
        universe = envelope.get("universe") if isinstance(envelope.get("universe"), dict) else {}
        with analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO research_runs (
                        run_id, workflow_type, status, strategy_id, strategy_version,
                        symbols, parameters, metrics_json, summary_json, warnings,
                        errors, artifacts_json, result_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        workflow_type = EXCLUDED.workflow_type,
                        status = EXCLUDED.status,
                        strategy_id = EXCLUDED.strategy_id,
                        strategy_version = EXCLUDED.strategy_version,
                        symbols = EXCLUDED.symbols,
                        parameters = EXCLUDED.parameters,
                        metrics_json = EXCLUDED.metrics_json,
                        summary_json = EXCLUDED.summary_json,
                        warnings = EXCLUDED.warnings,
                        errors = EXCLUDED.errors,
                        artifacts_json = EXCLUDED.artifacts_json,
                        result_json = EXCLUDED.result_json,
                        updated_at = NOW()
                    """,
                    (
                        run_id,
                        envelope.get("workflow_type"),
                        envelope.get("status"),
                        strategy.get("strategy_id"),
                        envelope.get("strategy_version"),
                        universe.get("symbols") if isinstance(universe.get("symbols"), list) else [],
                        Jsonb(envelope.get("parameters") or {}),
                        Jsonb(envelope.get("metrics") or {}),
                        Jsonb(envelope.get("summary") or {}),
                        envelope.get("warnings") or [],
                        envelope.get("errors") or [],
                        Jsonb(envelope.get("artifacts") or []),
                        Jsonb(envelope),
                    ),
                )
                for symbol in universe.get("symbols") or []:
                    cursor.execute(
                        """
                        INSERT INTO research_run_symbols (run_id, symbol)
                        VALUES (%s, %s)
                        ON CONFLICT (run_id, symbol) DO NOTHING
                        """,
                        (run_id, symbol),
                    )
        return {"saved": True, "run_id": run_id}

    def get_research_run(self, run_id: str) -> dict[str, Any] | None:
        with analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT result_json FROM research_runs WHERE run_id = %s", (run_id,))
                row = cursor.fetchone()
        if not row:
            return None
        return row[0]

    def list_research_runs(self, limit: int = 25) -> list[dict[str, Any]]:
        with analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT run_id, workflow_type, status, strategy_id, symbols, created_at, updated_at
                    FROM research_runs
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
        return [
            {
                "run_id": row[0],
                "workflow_type": row[1],
                "status": row[2],
                "strategy_id": row[3],
                "symbols": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "updated_at": row[6].isoformat() if row[6] else None,
            }
            for row in rows
        ]

