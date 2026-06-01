import type { BacktestResult } from "../api/client";
import DrawdownChart from "./DrawdownChart";
import EquityCurveChart from "./EquityCurveChart";
import MetricsCards from "./MetricsCards";
import MonteCarloChart from "./MonteCarloChart";
import PriceChart from "./PriceChart";
import TradesTable from "./TradesTable";

type ResultDashboardProps = {
  result: BacktestResult | null;
  isLoading: boolean;
  error: string | null;
};

export default function ResultDashboard({ result, isLoading, error }: ResultDashboardProps) {
  if (isLoading) {
    return (
      <div className="panel-shell flex min-h-[520px] items-center justify-center p-6">
        <div className="w-full max-w-lg">
          <div className="mb-4 h-2 overflow-hidden bg-line">
            <div className="h-full w-1/2 animate-pulse bg-cyan" />
          </div>
          <h2 className="mb-2 text-lg font-semibold text-text">Running deterministic backtest</h2>
          <p className="text-sm text-muted">Fetching cached or fresh Finnhub candles, generating signals, and building charts.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel-shell border-red/60 bg-red/10 p-5">
        <h2 className="mb-2 text-lg font-semibold text-red">Backtest failed</h2>
        <p className="text-sm leading-6 text-text">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="panel-shell flex min-h-[520px] items-center justify-center p-6">
        <div className="max-w-xl text-center">
          <h2 className="mb-3 text-xl font-semibold text-text">Run a strategy backtest</h2>
          <p className="text-sm leading-6 text-muted">
            Choose a symbol, select a strategy, adjust parameters, then run the backtest to populate metrics, charts,
            Monte Carlo paths, and trades.
          </p>
        </div>
      </div>
    );
  }

  const charts = result.charts || {};

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border border-line bg-panel px-4 py-3">
        <div>
          <div className="section-title">Backtest Complete</div>
          <div className="mt-1 text-sm text-muted">
            {result.request?.symbol || "Symbol"} / {result.request?.strategy || "Strategy"}
          </div>
        </div>
        <div className="text-sm text-green">{result.message || "Success"}</div>
      </div>

      {result.warnings?.length ? (
        <div className="border border-amber/50 bg-amber/10 px-4 py-3 text-sm text-amber">
          {result.warnings.join(", ")}
        </div>
      ) : null}

      <MetricsCards metrics={result.metrics} />

      <PriceChart price={charts.price} signals={charts.signals} />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <EquityCurveChart data={charts.equity_curve} />
        <DrawdownChart data={charts.drawdown_curve} />
      </div>

      <MonteCarloChart data={charts.monte_carlo} summary={result.summary} />

      <TradesTable trades={result.tables?.trades} />
    </div>
  );
}
