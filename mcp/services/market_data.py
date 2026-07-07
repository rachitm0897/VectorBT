from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.market_data import fetch_finnhub_candles_with_metadata, normalize_symbol
from tools.portfolio_optimization import fetch_multi_symbol_close_prices


class MarketDataService:
    def fetch_symbol(
        self,
        symbol: str,
        *,
        lookback: str,
        resolution: str,
        finnhub_api_key: str | None = None,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        return fetch_finnhub_candles_with_metadata(
            normalize_symbol(symbol),
            lookback=lookback,
            resolution=resolution,
            api_key=finnhub_api_key,
        )

    def fetch_aligned_closes(
        self,
        symbols: list[str],
        *,
        lookback: str,
        resolution: str,
        finnhub_api_key: str | None = None,
    ) -> pd.DataFrame:
        return fetch_multi_symbol_close_prices(
            symbols,
            lookback=lookback,
            resolution=resolution,
            finnhub_api_key=finnhub_api_key,
        )

    @staticmethod
    def data_quality(metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "candles_fetched": metadata.get("candles_fetched", 0),
            "start_date": metadata.get("start_date"),
            "end_date": metadata.get("end_date"),
            "cache_status": metadata.get("cache_status", "MISS"),
        }

    @staticmethod
    def align_return_series(series_by_symbol: dict[str, pd.Series]) -> pd.DataFrame:
        frame = pd.concat(series_by_symbol, axis=1, join="inner")
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if frame.empty:
            raise ValueError("No overlapping strategy returns were available.")
        return frame

