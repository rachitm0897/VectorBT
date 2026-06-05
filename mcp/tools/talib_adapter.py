from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import talib
from talib import abstract


REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def _prepare_talib_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Input data is missing required OHLCV columns: {', '.join(missing)}.")

    numeric = df.loc[:, REQUIRED_OHLCV_COLUMNS].copy()
    for column in REQUIRED_OHLCV_COLUMNS:
        numeric[column] = pd.to_numeric(numeric[column], errors="coerce")

    valid_rows = numeric.notna().all(axis=1)
    cleaned = numeric.loc[valid_rows].astype(float)
    if cleaned.empty:
        raise ValueError("Input data does not contain any valid OHLCV rows.")

    if "time" in df.columns:
        cleaned.index = pd.Index(df.loc[valid_rows, "time"].astype(str), name="time")
    return cleaned


def dataframe_to_talib_inputs(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Convert an OHLCV DataFrame into arrays accepted by TA-Lib's Abstract API."""
    cleaned = _prepare_talib_frame(df)
    return {
        column: cleaned[column].to_numpy(dtype=float)
        for column in REQUIRED_OHLCV_COLUMNS
    }


def list_talib_indicators() -> list[str]:
    return sorted(talib.get_functions())


def _normalize_indicator_name(indicator: str) -> str:
    normalized = str(indicator or "").strip().upper()
    if normalized not in talib.get_functions():
        raise ValueError(f"Unsupported TA-Lib indicator '{indicator}'.")
    return normalized


def get_talib_indicator_info(indicator: str) -> dict[str, Any]:
    normalized = _normalize_indicator_name(indicator)
    return dict(abstract.Function(normalized).info)


def compute_talib_indicator(
    df: pd.DataFrame,
    indicator: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, pd.Series]:
    normalized = _normalize_indicator_name(indicator)
    cleaned = _prepare_talib_frame(df)
    inputs = {
        column: cleaned[column].to_numpy(dtype=float)
        for column in REQUIRED_OHLCV_COLUMNS
    }
    function = abstract.Function(normalized)

    try:
        raw_outputs = function(inputs, **(parameters or {}))
    except Exception as exc:
        raise ValueError(f"Failed to compute TA-Lib indicator '{normalized}': {exc}") from exc

    output_names = list(function.output_names)
    values = [raw_outputs] if len(output_names) == 1 else list(raw_outputs)
    if len(values) != len(output_names):
        raise ValueError(
            f"TA-Lib indicator '{normalized}' returned {len(values)} outputs; "
            f"expected {len(output_names)}."
        )

    return {
        output_name: pd.Series(output, index=cleaned.index, name=output_name)
        for output_name, output in zip(output_names, values)
    }
