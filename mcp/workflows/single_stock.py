from __future__ import annotations

import uuid
from typing import Any

from schemas.results import ResearchResultEnvelope
from schemas.strategies import ExecutionType
from schemas.workflows import SingleStockResearchRequest
from services.artifacts import ArtifactService
from services.market_data import MarketDataService
from services.monte_carlo_engine import MonteCarloEngine
from services.persistence import PersistenceService
from services.signal_engine import SignalEngine
from services.strategy_registry import StrategyRegistryService
from services.strategy_validation import StrategyValidationService
from services.ui_spec_builder import UISpecBuilder
from services.vectorbt_engine import VectorBTEngine
from tools.formatting import series_to_points


class SingleStockResearchWorkflow:
    def __init__(self) -> None:
        self.registry = StrategyRegistryService()
        self.validator = StrategyValidationService()
        self.market_data = MarketDataService()
        self.signals = SignalEngine()
        self.vectorbt = VectorBTEngine()
        self.monte_carlo = MonteCarloEngine()
        self.artifacts = ArtifactService()
        self.persistence = PersistenceService()
        self.ui = UISpecBuilder()

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = SingleStockResearchRequest.model_validate(payload)
        run_id = f"research_{uuid.uuid4().hex[:8]}"
        strategy = self.registry.get(request.strategy_id)
        warnings: list[str] = []
        self.validator.validate_runnable(
            strategy,
            required_execution_type=ExecutionType.SINGLE_ASSET_SIGNAL,
        )
        parameters = self.validator.validate_parameters(strategy, request.parameters)

        df, metadata = self.market_data.fetch_symbol(
            request.symbol,
            lookback=request.lookback,
            resolution=request.resolution,
            finnhub_api_key=request.finnhub_api_key,
        )
        signal_payload = self.signals.generate_single_asset_signals(df, strategy, parameters)
        backtest = self.vectorbt.run_single_asset_backtest(
            df,
            signal_payload["entries"],
            signal_payload["exits"],
            initial_cash=request.initial_cash,
            fees=request.fees,
        )
        strategy_returns = self.vectorbt.equity_returns(backtest)
        mc_result = None
        if request.monte_carlo.enabled:
            request.monte_carlo.mode = "strategy_returns"
            mc_result = self.monte_carlo.simulate_returns(
                strategy_returns,
                start_value=float(backtest["metrics"]["final_value"]),
                settings=request.monte_carlo,
            )

        artifact_payload = {
            "run_id": run_id,
            "symbol": metadata["symbol"],
            "strategy": strategy.model_dump(mode="json", exclude_none=True),
            "parameters": parameters,
            "lookback": request.lookback,
            "resolution": request.resolution,
            "data_quality": self.market_data.data_quality(metadata),
            "ohlcv": df,
            "signals": _signals_artifact(signal_payload),
            "backtest": backtest,
            "strategy_returns": series_to_points(strategy_returns),
            "monte_carlo": mc_result,
        }
        artifact = self.artifacts.save_json(run_id, artifact_payload, artifact_type="single_stock_research")
        envelope = ResearchResultEnvelope(
            status="success",
            workflow_type="single_stock_research",
            run_id=run_id,
            strategy=_strategy_ref(strategy),
            strategy_version=strategy.implementation_version,
            universe={"symbols": [metadata["symbol"]]},
            parameters=parameters,
            data_quality=self.market_data.data_quality(metadata),
            summary={
                "symbol": metadata["symbol"],
                "strategy": strategy.name,
                "final_value": backtest["metrics"].get("final_value"),
                "total_return_pct": backtest["metrics"].get("total_return_pct"),
            },
            metrics=backtest["metrics"],
            trades=backtest.get("trades", [])[:200],
            equity=backtest.get("equity_curve", [])[:500],
            drawdown=backtest.get("drawdown_curve", [])[:500],
            monte_carlo=mc_result,
            warnings=[*warnings, *backtest.get("warnings", [])],
            artifacts=[artifact],
            ui_hint="single_stock_research",
            diagnostics={
                "monte_carlo_input": "strategy_equity_returns",
                "engine": "vectorbt",
            },
        )
        envelope.ui_spec = self.ui.build_for_envelope(envelope)
        envelope.persistence = self.persistence.persist_research_result(envelope)
        return envelope.model_dump(mode="json", exclude_none=True)


def _strategy_ref(strategy) -> dict[str, Any]:
    return {
        "strategy_id": strategy.strategy_id,
        "name": strategy.name,
        "execution_type": strategy.execution_type,
        "readiness": strategy.readiness,
    }


def _signals_artifact(signals: dict[str, Any]) -> dict[str, Any]:
    return {
        "entries": series_to_points(signals["entries"].astype(int)),
        "exits": series_to_points(signals["exits"].astype(int)),
        "indicators": {
            name: series_to_points(values)
            for name, values in (signals.get("indicators") or {}).items()
        },
    }

