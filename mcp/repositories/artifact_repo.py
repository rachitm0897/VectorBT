from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from repositories.base import analytics_connection


class ArtifactRepository:
    def save_artifact(self, artifact: dict[str, Any], run_id: str | None = None) -> None:
        with analytics_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ui_artifacts (
                        artifact_id, run_id, artifact_type, artifact_path,
                        artifact_url, summary_json, payload_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (artifact_id) DO UPDATE SET
                        run_id = EXCLUDED.run_id,
                        artifact_type = EXCLUDED.artifact_type,
                        artifact_path = EXCLUDED.artifact_path,
                        artifact_url = EXCLUDED.artifact_url,
                        summary_json = EXCLUDED.summary_json,
                        payload_json = EXCLUDED.payload_json,
                        updated_at = NOW()
                    """,
                    (
                        artifact.get("artifact_id"),
                        run_id,
                        artifact.get("artifact_type", "json"),
                        artifact.get("artifact_path"),
                        artifact.get("artifact_url"),
                        Jsonb(artifact.get("summary") or {}),
                        Jsonb(artifact),
                    ),
                )

