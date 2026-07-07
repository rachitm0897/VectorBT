from __future__ import annotations

from typing import Any

import pandas as pd

from schemas.strategies import CanonicalStrategy, ExecutionType
from tools.strategies import generate_strategy_signals


class SignalEngine:
    def supports_strategy(self, strategy: CanonicalStrategy) -> bool:
        return strategy.execution_type == ExecutionType.SINGLE_ASSET_SIGNAL

    def generate_single_asset_signals(
        self,
        df: pd.DataFrame,
        strategy: CanonicalStrategy,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.supports_strategy(strategy):
            raise ValueError(
                f"Strategy '{strategy.strategy_id}' is not a single-asset signal strategy."
            )
        return generate_strategy_signals(df, strategy.strategy_id, parameters or {})

