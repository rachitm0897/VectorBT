from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from repositories.base import analytics_connection


class DiscoveryRepository:
    def save_candidate(self, candidate: dict[str, Any]) -> None:
        with analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO strategy_candidates (
                        candidate_id, status, name, payload_json
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (candidate_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        name = EXCLUDED.name,
                        payload_json = EXCLUDED.payload_json,
                        updated_at = NOW()
                    """,
                    (
                        candidate.get("id") or candidate.get("candidate_id"),
                        candidate.get("status"),
                        (candidate.get("candidate") or {}).get("name") if isinstance(candidate.get("candidate"), dict) else candidate.get("name"),
                        Jsonb(candidate),
                    ),
                )
