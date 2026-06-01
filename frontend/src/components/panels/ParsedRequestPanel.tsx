import { memo } from "react";
import type { BacktestRequest, BacktestResult } from "../../api/client";
import SectionCard from "../layout/SectionCard";

type ParsedRequestPanelProps = {
  parsedRequest?: BacktestRequest | Record<string, unknown> | null;
  result?: BacktestResult | null;
};

function ParsedRequestPanel({ parsedRequest, result }: ParsedRequestPanelProps) {
  const request = asRecord(parsedRequest || result?.request || {});
  const parameters = asRecord(request.parameters);
  const monteCarlo = asRecord(request.monte_carlo);

  return (
    <SectionCard title="Parsed Request" subtitle="Read-only normalized strategy intent">
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
