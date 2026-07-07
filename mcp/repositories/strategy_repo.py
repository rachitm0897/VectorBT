from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from repositories.base import analytics_connection
from schemas.strategies import CanonicalStrategy


class StrategyRepository:
    def upsert_many(self, strategies: list[CanonicalStrategy]) -> dict[str, Any]:
        if not strategies:
            return {"upserted": 0}
        with analytics_connection() as conn:
            with conn.cursor() as cursor:
                for strategy in strategies:
                    payload = strategy.model_dump(mode="json")
                    cursor.execute(
                        """
                        INSERT INTO strategies (
                            strategy_id, name, aliases, description, family, category,
                            source_type, horizon_bucket, execution_type, readiness,
                            implementation_version, long_only, long_short, active,
                            deprecated, source_hash, template_hint, parameter_schema,
                            default_parameters, required_data, required_features,
                            signal_rules, ranking_rules, classification_metrics,
                            scores_json, source_payload
                        )
                        VALUES (
                            %(strategy_id)s, %(name)s, %(aliases)s, %(description)s,
                            %(family)s, %(category)s, %(source_type)s, %(horizon_bucket)s,
                            %(execution_type)s, %(readiness)s, %(implementation_version)s,
                            %(long_only)s, %(long_short)s, %(active)s, %(deprecated)s,
                            %(source_hash)s, %(template_hint)s, %(parameter_schema)s,
                            %(default_parameters)s, %(required_data)s, %(required_features)s,
                            %(signal_rules)s, %(ranking_rules)s, %(classification_metrics)s,
                            %(scores_json)s, %(source_payload)s
                        )
                        ON CONFLICT (strategy_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            aliases = EXCLUDED.aliases,
                            description = EXCLUDED.description,
                            family = EXCLUDED.family,
                            category = EXCLUDED.category,
                            source_type = EXCLUDED.source_type,
                            horizon_bucket = EXCLUDED.horizon_bucket,
                            execution_type = EXCLUDED.execution_type,
                            readiness = EXCLUDED.readiness,
                            implementation_version = EXCLUDED.implementation_version,
                            long_only = EXCLUDED.long_only,
                            long_short = EXCLUDED.long_short,
                            active = EXCLUDED.active,
                            deprecated = EXCLUDED.deprecated,
                            source_hash = EXCLUDED.source_hash,
                            template_hint = EXCLUDED.template_hint,
                            parameter_schema = EXCLUDED.parameter_schema,
                            default_parameters = EXCLUDED.default_parameters,
                            required_data = EXCLUDED.required_data,
                            required_features = EXCLUDED.required_features,
                            signal_rules = EXCLUDED.signal_rules,
                            ranking_rules = EXCLUDED.ranking_rules,
                            classification_metrics = EXCLUDED.classification_metrics,
                            scores_json = EXCLUDED.scores_json,
                            source_payload = EXCLUDED.source_payload,
                            updated_at = NOW()
                        """,
                        {
                            **payload,
                            "aliases": payload.get("aliases", []),
                            "execution_type": str(strategy.execution_type),
                            "readiness": str(strategy.readiness),
                            "parameter_schema": Jsonb(payload.get("parameter_schema") or {}),
                            "default_parameters": Jsonb(payload.get("default_parameters") or {}),
                            "required_data": payload.get("required_data", []),
                            "required_features": payload.get("required_features", []),
                            "signal_rules": Jsonb(payload.get("signal_rules") or {}),
                            "ranking_rules": Jsonb(payload.get("ranking_rules") or {}),
                            "classification_metrics": Jsonb(payload.get("classification_metrics") or {}),
                            "scores_json": Jsonb(
                                {
                                    "risk_score": payload.get("risk_score"),
                                    "return_score": payload.get("return_score"),
                                    "risk_adjusted_score": payload.get("risk_adjusted_score"),
                                    "robustness_score": payload.get("robustness_score"),
                                    "final_score": payload.get("final_score"),
                                }
                            ),
                            "source_payload": Jsonb(payload.get("source_payload") or {}),
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO strategy_versions (
                            strategy_id, implementation_version, source_hash, definition_json
                        )
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (strategy_id, implementation_version, source_hash) DO NOTHING
                        """,
                        (
                            strategy.strategy_id,
                            strategy.implementation_version,
                            strategy.source_hash,
                            Jsonb(payload),
                        ),
                    )
        return {"upserted": len(strategies)}

