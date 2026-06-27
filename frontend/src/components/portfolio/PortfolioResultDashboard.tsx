import type { BacktestRequest, PortfolioOptimizationRequest, PortfolioResult } from "../../api/client";
import EmptyState from "../layout/EmptyState";
import ErrorState from "../layout/ErrorState";
import LoadingState from "../layout/LoadingState";
import SectionCard from "../layout/SectionCard";
import CorrelationHeatmap from "./CorrelationHeatmap";
import EfficientFrontierChart from "./EfficientFrontierChart";
import PortfolioMetricsCards from "./PortfolioMetricsCards";
import PortfolioScenarioAnalysis from "./PortfolioScenarioAnalysis";
import PortfolioWeightsChart from "./PortfolioWeightsChart";

type PortfolioResultDashboardProps = {
  result: PortfolioResult | null;
  isLoading: boolean;
  error: string | null;
  parsedRequest?: BacktestRequest | PortfolioOptimizationRequest | Record<string, unknown> | null;
};

export default function PortfolioResultDashboard({
  result,
  isLoading,
  error,
  parsedRequest,
}: PortfolioResultDashboardProps) {
  if (isLoading) return <LoadingState label="Running portfolio optimization" />;
  if (error && !result) return <ErrorState message={error} />;
  if (!result) {
    return (
      <EmptyState
        title="No portfolio optimization loaded"
        message="Select symbols from all stocks, filter by sector, or enter tickers manually to run Markowitz optimization."
      />
    );
  }

  const symbolsUsed = result.symbols_used?.length ? result.symbols_used : result.symbols || [];
  const selectionMessage =
    result.selection_mode === "sector" && result.sector
      ? `Optimized using all ${result.sector} stocks in the universe.`
      : "Optimized using selected symbols.";

  return (
    <div className="space-y-4">
      {error ? <ErrorState message={error} /> : null}
      <PortfolioMetricsCards result={result} />
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <EfficientFrontierChart result={result} />
        <PortfolioWeightsChart result={result} />
      </div>
      <PortfolioScenarioAnalysis result={result} />
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <CorrelationHeatmap result={result} />
        <SectionCard title="Portfolio Details" subtitle={result.objective || "markowitz"}>
          <div className="space-y-3 text-sm">
            <div className="border border-cyan/50 bg-cyan/10 px-3 py-2 text-xs leading-5 text-cyan">
              {selectionMessage}
            </div>
            <DetailRow label="Mode" value={result.selection_mode || "symbols"} />
            <DetailRow label="Sector" value={result.sector || "-"} />
            <DetailRow label="Symbols Used" value={symbolsUsed.join(", ") || "-"} />
            <DetailRow label="Symbol Count" value={String(symbolsUsed.length || "-")} />
            <DetailRow label="Rejected" value={(result.rejected_symbols || []).join(", ") || "-"} />
            <DetailRow label="Rows Used" value={String(result.data_quality?.rows_used || "-")} />
            <DetailRow label="Date Range" value={dateRange(result.data_quality)} />
            {result.artifact_url ? (
              <a
                className="block break-all border border-line bg-ink px-3 py-2 font-mono text-xs text-cyan transition hover:border-cyan"
                href={result.artifact_url}
                target="_blank"
                rel="noreferrer"
              >
                {result.artifact_url}
              </a>
            ) : null}
            {(result.warnings || []).map((warning) => (
              <div key={warning} className="border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
                {warning}
              </div>
            ))}
            {parsedRequest ? (
              <pre className="max-h-72 overflow-auto border border-line bg-ink p-3 text-xs leading-5 text-muted">
                {JSON.stringify(parsedRequest, null, 2)}
              </pre>
            ) : null}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border border-line bg-ink px-3 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{label}</span>
      <span className="break-words text-right font-mono text-xs text-text">{value}</span>
    </div>
  );
}

function dateRange(data: Record<string, unknown> | undefined): string {
  const start = data?.start_date ? String(data.start_date) : "";
  const end = data?.end_date ? String(data.end_date) : "";
  return start && end ? `${start} to ${end}` : "-";
}
