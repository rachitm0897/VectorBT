import { memo } from "react";
import type { BacktestResult } from "../../api/client";
import SectionCard from "../layout/SectionCard";

type StrategySummaryPanelProps = {
  result: BacktestResult;
};

function StrategySummaryPanel({ result }: StrategySummaryPanelProps) {
  return (
    <SectionCard title="Strategy Summary" subtitle={result.message || "Backtest completed"}>
      <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
        <SummaryCell label="Symbol" value={result.request?.symbol} />
        <SummaryCell label="Strategy" value={result.request?.strategy} />
        <SummaryCell label="Parameters" value={JSON.stringify(result.request?.parameters || {})} mono />
      </div>
      {result.warnings?.length ? (
        <div className="mt-3 border border-amber/50 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
          {result.warnings.join(", ")}
        </div>
      ) : null}
    </SectionCard>
  );
}

function SummaryCell({ label, value, mono }: { label: string; value: unknown; mono?: boolean }) {
  return (
    <div className="border border-line bg-ink px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className={`mt-1 truncate text-text ${mono ? "font-mono text-xs" : "font-semibold"}`}>{String(value ?? "-")}</div>
    </div>
  );
}

export default memo(StrategySummaryPanel);
