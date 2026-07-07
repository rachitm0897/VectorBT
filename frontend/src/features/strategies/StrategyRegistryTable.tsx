import { useMemo, useState } from "react";
import type { StrategyRegistryItem, StrategyRegistrySummary } from "../../api/client";

type StrategyRegistryTableProps = {
  strategies: StrategyRegistryItem[];
  summary: StrategyRegistrySummary | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSync?: () => void;
  onSelectStrategy?: (strategyId: string) => void;
};

const statuses = ["all", "executable", "catalogue_only", "missing_data", "incomplete_rules", "failed", "deprecated"];

export default function StrategyRegistryTable({
  strategies,
  summary,
  isLoading,
  error,
  onRefresh,
  onSync,
  onSelectStrategy,
}: StrategyRegistryTableProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [executionType, setExecutionType] = useState("all");
  const [source, setSource] = useState("all");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return strategies.filter((strategy) => {
      if (status !== "all" && strategy.usability_status !== status) return false;
      if (executionType !== "all" && strategy.execution_type !== executionType) return false;
      if (source === "built_in" && strategy.source_type !== "built_in") return false;
      if (source === "imported" && strategy.source_type === "built_in") return false;
      if (!q) return true;
      return [strategy.strategy_id, strategy.name, strategy.family, strategy.description, strategy.source_type]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [executionType, query, source, status, strategies]);
  const executionTypes = useMemo(
    () => Array.from(new Set(strategies.map((strategy) => strategy.execution_type).filter(Boolean).map(String))).sort(),
    [strategies],
  );

  return (
    <section className="panel-shell">
      <div className="border-b border-line p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="section-title">Strategy Registry</h2>
            <CounterStrip summary={summary} fallbackTotal={strategies.length} />
          </div>
          <div className="flex gap-2">
            <button className="terminal-button" type="button" onClick={onRefresh} disabled={isLoading}>
              {isLoading ? "Loading" : "Reload Catalogue"}
            </button>
            {onSync ? (
              <button className="terminal-button terminal-button-green" type="button" onClick={onSync} disabled={isLoading}>
                Sync Strategy Registry
              </button>
            ) : null}
          </div>
        </div>
        {error ? <div className="mt-3 border border-red/60 bg-red/10 p-3 text-xs text-red">{error}</div> : null}
      </div>

      <div className="grid gap-3 border-b border-line p-4 lg:grid-cols-[minmax(240px,1fr)_180px_220px_160px]">
        <label className="space-y-2">
          <span className="form-label">Search</span>
          <input className="form-control font-mono" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <Select label="Status" value={status} onChange={setStatus} options={statuses} />
        <Select label="Execution Type" value={executionType} onChange={setExecutionType} options={["all", ...executionTypes]} />
        <Select label="Source" value={source} onChange={setSource} options={["all", "built_in", "imported"]} />
      </div>

      <div className="max-h-[520px] overflow-auto">
        <table className="min-w-full border-collapse font-mono text-xs">
          <thead className="sticky top-0 bg-panel2 text-muted">
            <tr>
              <HeaderCell>ID</HeaderCell>
              <HeaderCell>Name</HeaderCell>
              <HeaderCell>Status</HeaderCell>
              <HeaderCell>Readiness</HeaderCell>
              <HeaderCell>Execution</HeaderCell>
              <HeaderCell>Source</HeaderCell>
              <HeaderCell>Score</HeaderCell>
              <HeaderCell>Run</HeaderCell>
            </tr>
          </thead>
          <tbody>
            {filtered.map((strategy) => {
              const executable = Boolean(strategy.executable || strategy.runnable);
              return (
                <tr key={strategy.strategy_id} className="odd:bg-ink even:bg-panel">
                  <td className="border-b border-line px-3 py-2 text-green">{strategy.strategy_id}</td>
                  <td className="border-b border-line px-3 py-2 text-text">
                    <div>{strategy.name}</div>
                    <div className="mt-1 max-w-xl truncate text-[11px] text-muted">{strategy.description}</div>
                  </td>
                  <td className="border-b border-line px-3 py-2">
                    <StatusBadge status={strategy.usability_status || (executable ? "executable" : "catalogue_only")} label={strategy.status_label} />
                  </td>
                  <td className="border-b border-line px-3 py-2 text-muted">{strategy.readiness || "-"}</td>
                  <td className="border-b border-line px-3 py-2 text-muted">{strategy.execution_type || "-"}</td>
                  <td className="border-b border-line px-3 py-2 text-muted">{strategy.source_type || "-"}</td>
                  <td className="border-b border-line px-3 py-2 text-muted">{formatScore(strategy.final_score)}</td>
                  <td className="border-b border-line px-3 py-2">
                    <button
                      className="terminal-button px-2 py-1"
                      type="button"
                      disabled={!executable}
                      onClick={() => onSelectStrategy?.(strategy.strategy_id)}
                      title={executable ? "Use this strategy in Manual Research Lab" : "This strategy is visible but cannot be run by current workflows"}
                    >
                      {executable ? "Use" : "Disabled"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CounterStrip({ summary, fallbackTotal }: { summary: StrategyRegistrySummary | null; fallbackTotal: number }) {
  const counters = [
    ["Total", summary?.total_strategies ?? fallbackTotal],
    ["Executable", summary?.executable_strategies ?? 0],
    ["Catalogue-only", summary?.catalogue_only_strategies ?? 0],
    ["Imported", summary?.imported_strategies ?? 0],
    ["Built-in", summary?.built_in_strategies ?? 0],
    ["Failed Imports", summary?.failed_imports ?? 0],
  ];
  return (
    <div className="mt-3 flex flex-wrap gap-2 font-mono text-[11px]">
      {counters.map(([label, value]) => (
        <span key={String(label)} className="border border-line bg-ink px-2 py-1 text-muted">
          {label}: <span className="text-text">{String(value)}</span>
        </span>
      ))}
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2">
      <span className="form-label">{label}</span>
      <select className="form-control font-mono" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option.replace(/_/g, " ")}
          </option>
        ))}
      </select>
    </label>
  );
}

function HeaderCell({ children }: { children: string }) {
  return <th className="border-b border-line px-3 py-2 text-left font-semibold uppercase">{children}</th>;
}

function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone = {
    executable: "border-green/50 text-green",
    catalogue_only: "border-muted/40 text-muted",
    missing_data: "border-amber/50 text-amber",
    incomplete_rules: "border-amber/50 text-amber",
    failed: "border-red/50 text-red",
    deprecated: "border-red/50 text-red",
  }[status] || "border-line text-muted";
  return <span className={`inline-block border px-2 py-1 ${tone}`}>{label || status.replace(/_/g, " ")}</span>;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "-";
}
