from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tools.cache import SERVER_ROOT, cache_dir


def _clean_scalar(value: Any) -> Any:
    if value is pd.NaT:
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


def _jsonable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return [_jsonable(record) for record in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return series_to_points(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return _clean_scalar(value)


def series_to_points(series: pd.Series) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, value in pd.Series(series).items():
        points.append({"time": str(index), "value": _clean_scalar(value)})
    return points


def _relative_artifact_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(SERVER_ROOT.parent).as_posix()
    except ValueError:
        return resolved.as_posix()


def save_artifact_json(run_id: str, artifact: dict[str, Any]) -> str:
    path = cache_dir("results") / f"{run_id}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_jsonable(artifact), handle, indent=2, sort_keys=True)
    return _relative_artifact_path(path)


def _artifact_id(artifact_path: str) -> str:
    return Path(artifact_path).name


def _artifact_url(artifact_path: str) -> str | None:
    public_base_url = os.getenv("MCP_PUBLIC_BASE_URL", "").rstrip("/")
    if not public_base_url:
        return None
    return f"{public_base_url}/artifacts/{_artifact_id(artifact_path)}"


def _artifact_fields(artifact_path: str) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "artifact_path": artifact_path,
        "artifact_id": _artifact_id(artifact_path),
    }
    url = _artifact_url(artifact_path)
    if url:
        fields["artifact_url"] = url
    return fields


def compact_backtest_response(
    run_id: str,
    symbol: str,
    strategy: str,
    parameters: dict[str, Any],
    lookback: str,
    metrics: dict[str, Any],
    data_quality: dict[str, Any],
    artifact_path: str,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "status": "success",
        "run_id": run_id,
        "symbol": symbol,
        "strategy": strategy,
        "parameters": parameters,
        "lookback": lookback,
        "metrics": metrics,
        "data_quality": data_quality,
        **_artifact_fields(artifact_path),
        "warnings": warnings,
    }


def compact_monte_carlo_response(
    symbol: str,
    method: str,
    days: int,
    simulations: int,
    summary: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    return {
        "status": "success",
        "symbol": symbol,
        "method": method,
        "days": days,
        "simulations": simulations,
        "summary": summary,
        **_artifact_fields(artifact_path),
    }


def compact_research_response(
    run_id: str,
    symbol: str,
    strategy: str,
    parameters: dict[str, Any],
    backtest: dict[str, Any],
    monte_carlo: dict[str, Any] | None,
    data_quality: dict[str, Any],
    artifact_path: str,
    warnings: list[str],
) -> dict[str, Any]:
    response = {
        "status": "success",
        "run_id": run_id,
        "symbol": symbol,
        "strategy": strategy,
        "parameters": parameters,
        "backtest": backtest,
        "data_quality": {
            "candles_fetched": data_quality.get("candles_fetched"),
            "cache_status": data_quality.get("cache_status"),
        },
        **_artifact_fields(artifact_path),
        "warnings": warnings,
    }
    if monte_carlo is not None:
        response["monte_carlo"] = {
            "expected_return_pct": monte_carlo.get("expected_return_pct"),
            "probability_positive_return_pct": monte_carlo.get(
                "probability_positive_return_pct"
            ),
            "p5_return_pct": monte_carlo.get("p5_return_pct"),
            "p95_return_pct": monte_carlo.get("p95_return_pct"),
        }
    return response
