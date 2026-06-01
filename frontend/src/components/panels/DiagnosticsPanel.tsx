import { memo, useState } from "react";
import type { BacktestResult } from "../../api/client";
import SectionCard from "../layout/SectionCard";

type DiagnosticsPanelProps = {
  result: BacktestResult | null;
  diagnostics?: Record<string, unknown> | null;
  error?: string | null;
};

function DiagnosticsPanel({ result, diagnostics, error }: DiagnosticsPanelProps) {
  const [showJson, setShowJson] = useState(false);
  const merged = {
    data_source: diagnostics?.data_source ?? "Finnhub",
    cache_status: diagnostics?.cache_status ?? "not reported",
    candles_fetched: diagnostics?.candles_fetched ?? result?.charts?.price?.length ?? 0,
    start_date: diagnostics?.start_date ?? firstDate(result),
    end_date: diagnostics?.end_date ?? lastDate(result),
    missing_data_count: diagnostics?.missing_data_count ?? "-",
  };

  return (
    <SectionCard
      title="Diagnostics"
      subtitle="Data, cache, warnings, errors"
      action={
        <button className="border border-line px-2 py-1 text-[11px] uppercase tracking-[0.12em] text-muted" type="button" onClick={() => setShowJson((value) => !value)}>
          {showJson ? "Hide JSON" : "Debug JSON"}
        </button>
      }
    >
      <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-3">
        {Object.entries(merged).map(([key, value]) => (
          <div key={key} className="border border-line bg-ink px-3 py-2">
            <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{key.replaceAll("_", " ")}</div>
            <div className="mt-1 font-mono text-text">{String(value ?? "-")}</div>
          </div>
        ))}
      </div>
      {result?.warnings?.length ? <Message tone="warn" label="Warnings" value={result.warnings.join(", ")} /> : null}
      {result?.errors?.length ? <Message tone="error" label="Errors" value={result.errors.join(", ")} /> : null}
      {error ? <Message tone="error" label="UI Error" value={error} /> : null}
      {showJson ? (
        <pre className="mt-3 max-h-96 overflow-auto border border-line bg-ink p-3 text-[11px] leading-5 text-muted">
          {JSON.stringify({ diagnostics, result }, null, 2)}
        </pre>
      ) : null}
    </SectionCard>
  );
}

function Message({ tone, label, value }: { tone: "warn" | "error"; label: string; value: string }) {
  return (
    <div className={`mt-3 border px-3 py-2 text-xs ${tone === "warn" ? "border-amber/50 bg-amber/10 text-amber" : "border-red/60 bg-red/10 text-red"}`}>
      <span className="font-semibold">{label}: </span>
      {value}
    </div>
  );
}

function firstDate(result: BacktestResult | null) {
  return result?.charts?.price?.[0]?.time || result?.charts?.price?.[0]?.date || "-";
}

function lastDate(result: BacktestResult | null) {
  const price = result?.charts?.price || [];
  return price[price.length - 1]?.time || price[price.length - 1]?.date || "-";
}

export default memo(DiagnosticsPanel);
