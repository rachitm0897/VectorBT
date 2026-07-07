from __future__ import annotations

from typing import Any

from schemas.workflows import StrategyComparisonRequest
from workflows.single_stock import SingleStockResearchWorkflow


class StrategyComparisonWorkflow:
    def __init__(self) -> None:
        self.single_stock = SingleStockResearchWorkflow()

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = StrategyComparisonRequest.model_validate(payload)
        runs: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for strategy_id in request.strategy_ids:
            try:
                result = self.single_stock.run(
                    {
                        "symbol": request.symbol,
                        "strategy_id": strategy_id,
                        "parameters": request.parameters_by_strategy.get(strategy_id, {}),
                        "lookback": request.lookback,
                        "resolution": request.resolution,
                        "initial_cash": request.initial_cash,
                        "fees": request.fees,
                        "monte_carlo": {"enabled": False},
                        "finnhub_api_key": request.finnhub_api_key,
                    }
                )
                runs.append(result)
            except Exception as exc:
                errors.append({"strategy_id": strategy_id, "message": str(exc)})
        return {
            "status": "success" if runs else "error",
            "workflow_type": "strategy_comparison",
            "symbol": request.symbol,
            "runs": runs,
            "errors": errors,
            "comparison": _comparison_rows(runs),
        }


def _comparison_rows(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
        strategy = run.get("strategy") if isinstance(run.get("strategy"), dict) else {}
        rows.append(
            {
                "run_id": run.get("run_id"),
                "strategy_id": strategy.get("strategy_id"),
                "strategy_name": strategy.get("name"),
                "total_return_pct": metrics.get("total_return_pct"),
                "sharpe_ratio": metrics.get("sharpe_ratio"),
                "max_drawdown_pct": metrics.get("max_drawdown_pct"),
                "final_value": metrics.get("final_value"),
            }
        )
    return rows
