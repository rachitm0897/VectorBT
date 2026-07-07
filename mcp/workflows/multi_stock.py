from __future__ import annotations

import uuid
from typing import Any

import pandas as pd

from schemas.results import ResearchResultEnvelope
from schemas.strategies import ExecutionType
from schemas.workflows import MultiStockResearchRequest
from services.artifacts import ArtifactService
from services.market_data import MarketDataService
from services.monte_carlo_engine import MonteCarloEngine
from services.persistence import PersistenceService
from services.portfolio_optimizer import PortfolioOptimizer
from services.signal_engine import SignalEngine
from services.strategy_registry import StrategyRegistryService
from services.strategy_validation import StrategyValidationService
from services.ui_spec_builder import UISpecBuilder
from services.vectorbt_engine import VectorBTEngine
from tools.market_data import normalize_symbol


class MultiStockResearchWorkflow:
    def __init__(self) -> None:
        self.registry = StrategyRegistryService()
        self.validator = StrategyValidationService()
        self.market_data = MarketDataService()
        self.signals = SignalEngine()
        self.vectorbt = VectorBTEngine()
        self.optimizer = PortfolioOptimizer()
        self.monte_carlo = MonteCarloEngine()
        self.artifacts = ArtifactService()
        self.persistence = PersistenceService()
        self.ui = UISpecBuilder()

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = MultiStockResearchRequest.model_validate(payload)
        run_id = f"multi_research_{uuid.uuid4().hex[:8]}"
        strategy = self.registry.get(request.strategy_id)
        self.validator.validate_runnable(
            strategy,
            required_execution_type=ExecutionType.SINGLE_ASSET_SIGNAL,
        )
        parameters = self.validator.validate_parameters(strategy, request.parameters)
        symbols = _normalize_symbols(request.symbols)

        returns_by_symbol: dict[str, pd.Series] = {}
        per_symbol: dict[str, Any] = {}
        data_quality: dict[str, Any] = {}
        warnings: list[str] = []
        for symbol in symbols:
            df, metadata = self.market_data.fetch_symbol(
                symbol,
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
            returns_by_symbol[metadata["symbol"]] = strategy_returns
            data_quality[metadata["symbol"]] = self.market_data.data_quality(metadata)
            per_symbol[metadata["symbol"]] = {
                "metrics": backtest["metrics"],
                "warnings": backtest.get("warnings", []),
            }
            warnings.extend(f"{metadata['symbol']}:{item}" for item in backtest.get("warnings", []))

        strategy_returns = self.market_data.align_return_series(returns_by_symbol)
        optimization = self.optimizer.optimize_returns(strategy_returns, request.optimization)
        portfolio_backtest = self.vectorbt.run_weighted_portfolio_backtest(
            strategy_returns,
            optimization["weights"],
            initial_cash=request.initial_cash,
        )
        mc_result = None
        if request.monte_carlo.enabled:
            request.monte_carlo.mode = "portfolio_returns"
            mc_result = self.monte_carlo.simulate_returns(
                portfolio_backtest["returns"],
                start_value=float(portfolio_backtest["metrics"]["final_value"]),
                settings=request.monte_carlo,
            )

        artifact_payload = {
            "run_id": run_id,
            "symbols": list(strategy_returns.columns),
            "strategy": strategy.model_dump(mode="json", exclude_none=True),
            "parameters": parameters,
            "lookback": request.lookback,
            "resolution": request.resolution,
            "data_quality": data_quality,
            "per_symbol": per_symbol,
            "strategy_returns": strategy_returns.reset_index().to_dict(orient="records"),
            "optimization": optimization,
            "portfolio_backtest": {
                key: value
                for key, value in portfolio_backtest.items()
                if key != "returns"
            },
            "portfolio_returns": portfolio_backtest["returns"],
            "monte_carlo": mc_result,
        }
        artifact = self.artifacts.save_json(run_id, artifact_payload, artifact_type="multi_stock_research")
        envelope = ResearchResultEnvelope(
            status="success",
            workflow_type="multi_stock_research",
            run_id=run_id,
            strategy={
                "strategy_id": strategy.strategy_id,
                "name": strategy.name,
                "execution_type": strategy.execution_type,
                "readiness": strategy.readiness,
            },
            strategy_version=strategy.implementation_version,
            universe={"symbols": list(strategy_returns.columns)},
            parameters=parameters,
            data_quality={"symbols": data_quality, "aligned_rows": int(len(strategy_returns))},
            summary={
                "strategy": strategy.name,
                "symbols": list(strategy_returns.columns),
                "final_value": portfolio_backtest["metrics"].get("final_value"),
                "total_return_pct": portfolio_backtest["metrics"].get("total_return_pct"),
            },
            metrics=portfolio_backtest["metrics"],
            allocations={"weights": optimization["weights"], "optimizer_metrics": optimization["metrics"]},
            equity=portfolio_backtest.get("equity_curve", [])[:500],
            drawdown=portfolio_backtest.get("drawdown_curve", [])[:500],
            monte_carlo=mc_result,
            frontier=optimization.get("frontier", [])[:300],
            warnings=[*warnings, *optimization.get("warnings", [])],
            artifacts=[artifact],
            ui_hint="optimized_multi_stock_portfolio",
            diagnostics={
                "optimizer_input": "aligned_strategy_returns",
                "monte_carlo_input": "optimized_portfolio_returns",
                "per_symbol": per_symbol,
                "correlation_matrix": optimization.get("correlation_matrix", []),
                "min_volatility_portfolio": optimization.get("min_volatility_portfolio"),
                "max_sharpe_portfolio": optimization.get("max_sharpe_portfolio"),
            },
        )
        envelope.ui_spec = self.ui.build_for_envelope(envelope)
        envelope.persistence = self.persistence.persist_research_result(envelope)
        return envelope.model_dump(mode="json", exclude_none=True)


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        cleaned = normalize_symbol(symbol)
        if cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    if len(normalized) < 2:
        raise ValueError("At least two unique symbols are required.")
    return normalized
