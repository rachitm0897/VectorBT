import type { AnalyticsStatus, MCPStatus, StrategyRegistrySummary } from "../../api/client";

type StatusBarProps = {
  mcpStatus: MCPStatus | null;
  analyticsStatus: AnalyticsStatus | null;
  registrySummary: StrategyRegistrySummary | null;
};

export default function StatusBar({ mcpStatus, analyticsStatus, registrySummary }: StatusBarProps) {
  return (
    <footer className="flex flex-wrap items-center gap-2 border-t border-line bg-ink px-3 py-2 font-mono text-[11px] text-muted">
      <StatusPill label="Backend" value="OK" tone="green" />
      <StatusPill
        label="MCP"
        value={mcpStatus?.connected ? "Connected" : mcpStatus?.enabled === false ? "Disabled" : "Unknown"}
        tone={mcpStatus?.connected ? "green" : "amber"}
      />
      <StatusPill
        label="Analytics"
        value={analyticsStatus?.connected ? "Connected" : analyticsStatus?.enabled === false ? "Disabled" : "Unknown"}
        tone={analyticsStatus?.connected ? "green" : "amber"}
      />
      <StatusPill label="Strategies" value={String(registrySummary?.total_strategies ?? "-")} />
      <StatusPill label="Executable" value={String(registrySummary?.executable_strategies ?? "-")} tone="green" />
      <StatusPill label="Failed Imports" value={String(registrySummary?.failed_imports ?? "-")} tone="red" />
    </footer>
  );
}

function StatusPill({
  label,
  value,
  tone = "muted",
}: {
  label: string;
  value: string;
  tone?: "green" | "amber" | "red" | "muted";
}) {
  const color = {
    green: "text-green border-green/40",
    amber: "text-amber border-amber/40",
    red: "text-red border-red/40",
    muted: "text-muted border-line",
  }[tone];
  return (
    <span className={`border bg-panel px-2 py-1 ${color}`}>
      <span className="text-muted">{label}:</span> {value}
    </span>
  );
}
