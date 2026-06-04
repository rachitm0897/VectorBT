import { memo } from "react";
import type { BacktestRequest, BacktestResult, PortfolioOptimizationRequest } from "../../api/client";
import SectionCard from "../layout/SectionCard";

type ParsedRequestPanelProps = {
  parsedRequest?: BacktestRequest | PortfolioOptimizationRequest | Record<string, unknown> | null;
  result?: BacktestResult | null;
  variant?: "card" | "plain";
};

function ParsedRequestPanel({ parsedRequest, result, variant = "card" }: ParsedRequestPanelProps) {
  const request = asRecord(parsedRequest || result?.request || {});
  const isPortfolio = request.request_type === "portfolio_optimization" || Array.isArray(request.symbols);
  const parameters = asRecord(request.parameters);
  const monteCarlo = asRecord(request.monte_carlo);

  const body = (
    <>
      {isPortfolio ? (
        <div className="space-y-2 text-xs">
          <Row label="Symbols" value={Array.isArray(request.symbols) ? request.symbols.join(", ") : undefined} />
          <Row label="Lookback" value={request.lookback} />
          <Row label="Objective" value={request.objective} />
          <Row label="Risk-Free" value={request.risk_free_rate} />
          <Row label="Max Weight" value={request.max_weight} />
          <Row label="Allow Short" value={request.allow_short} />
          <Row label="Frontier" value={request.num_frontier_portfolios} />
        </div>
      ) : (
        <div className="space-y-2 text-xs">
          <Row label="Symbol" value={request.symbol} />
          <Row label="Strategy" value={request.strategy} />
          <Row label="Lookback" value={request.lookback} />
          <Row label="Initial Cash" value={request.initial_cash} />
          <Row label="Fees" value={request.fees} />
          <Row label="Monte Carlo" value={monteCarlo.days ? `${monteCarlo.days}d / ${monteCarlo.simulations} sims` : undefined} />
          <div className="border-t border-line pt-2">
            <div className="mb-1 text-[10px] uppercase tracking-[0.14em] text-muted">Parameters</div>
            <div className="font-mono text-[11px] leading-5 text-text">
              {Object.keys(parameters).length ? JSON.stringify(parameters) : "{}"}
            </div>
          </div>
        </div>
      )}
    </>
  );

  if (variant === "plain") {
    return body;
  }

  return (
    <SectionCard title="Parsed Request" subtitle={isPortfolio ? "Read-only normalized portfolio intent" : "Read-only normalized strategy intent"}>
      {body}
    </SectionCard>
  );
}

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line/70 pb-1">
      <span className="text-muted">{label}</span>
      <span className="truncate text-right font-mono text-text">{value === undefined || value === null || value === "" ? "-" : String(value)}</span>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export default memo(ParsedRequestPanel);
