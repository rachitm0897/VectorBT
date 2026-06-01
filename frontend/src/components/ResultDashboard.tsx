import { useState } from "react";
import type { BacktestRequest, BacktestResult } from "../api/client";
import DrawdownUnderwaterChart from "./charts/DrawdownUnderwaterChart";
import EquityBenchmarkChart from "./charts/EquityBenchmarkChart";
import MonteCarloFanChart from "./charts/MonteCarloFanChart";
import MonteCarloHistogram from "./charts/MonteCarloHistogram";
import MonthlyReturnsHeatmap from "./charts/MonthlyReturnsHeatmap";
import ParameterHeatmap from "./charts/ParameterHeatmap";
import PremiumPriceChart from "./charts/PremiumPriceChart";
import RollingMetricsChart from "./charts/RollingMetricsChart";
import TradeDistributionChart from "./charts/TradeDistributionChart";
import DashboardTabs, { type DashboardTab } from "./layout/DashboardTabs";
import EmptyState from "./layout/EmptyState";
import ErrorState from "./layout/ErrorState";
import LoadingState from "./layout/LoadingState";
import DiagnosticsPanel from "./panels/DiagnosticsPanel";
import MetricsStrip from "./panels/MetricsStrip";
import ParsedRequestPanel from "./panels/ParsedRequestPanel";
import StrategySummaryPanel from "./panels/StrategySummaryPanel";
import TokenUsagePanel from "./panels/TokenUsagePanel";
import TradesGrid from "./tables/TradesGrid";

type ResultDashboardProps = {
  result: BacktestResult | null;
  isLoading: boolean;
  error: string | null;
  parsedRequest?: BacktestRequest | Record<string, unknown> | null;
  diagnostics?: Record<string, unknown> | null;
  usedChat?: boolean;
};

export default function ResultDashboard({
  result,
  isLoading,
  error,
  parsedRequest,
  diagnostics,
  usedChat,
}: ResultDashboardProps) {
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");

  if (isLoading) return <LoadingState label="Running deterministic analytics pipeline" />;
  if (error && !result) return <ErrorState message={error} />;
  if (!result) {
    return (
      <EmptyState
        title="No backtest loaded"
        message="Run a manual strategy or submit a natural-language chat request to populate the terminal."
      />
    );
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorState message={error} /> : null}
      <MetricsStrip result={result} />
      <PremiumPriceChart result={result} />
      <DashboardTabs activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === "overview" ? (
        <div className="space-y-4">
          <StrategySummaryPanel result={result} />
          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
            <EquityBenchmarkChart result={result} />
            <DrawdownUnderwaterChart result={result} />
          </div>
          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
            <MonthlyReturnsHeatmap result={result} />
            <RollingMetricsChart result={result} />
          </div>
        </div>
      ) : null}

      {activeTab === "backtest" ? (
        <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
          <EquityBenchmarkChart result={result} />
          <DrawdownUnderwaterChart result={result} />
          <TradeDistributionChart result={result} />
          <RollingMetricsChart result={result} />
        </div>
      ) : null}

      {activeTab === "monteCarlo" ? (
        <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
          <MonteCarloFanChart result={result} />
          <MonteCarloHistogram result={result} />
        </div>
      ) : null}

      {activeTab === "parameters" ? (
        <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_360px]">
          <ParameterHeatmap result={result} />
          <ParsedRequestPanel parsedRequest={parsedRequest} result={result} />
        </div>
      ) : null}

      {activeTab === "trades" ? (
        <div className="space-y-4">
          <TradesGrid result={result} />
          <TradeDistributionChart result={result} />
        </div>
      ) : null}

      {activeTab === "diagnostics" ? (
        <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_360px]">
          <DiagnosticsPanel result={result} diagnostics={diagnostics || result.diagnostics} error={error} />
          <TokenUsagePanel diagnostics={diagnostics || result.diagnostics} usedChat={usedChat} />
        </div>
      ) : null}
    </div>
  );
}
