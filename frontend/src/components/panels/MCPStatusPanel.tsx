import { memo } from "react";
import type { MCPStatus } from "../../api/client";
import SectionCard from "../layout/SectionCard";

type MCPStatusPanelProps = {
  status: MCPStatus | null;
  isLoading: boolean;
  error: string | null;
};

function MCPStatusPanel({ status, isLoading, error }: MCPStatusPanelProps) {
  const label = statusLabel(status, isLoading, error);
  const toneClass = status?.enabled && status.connected ? "text-green" : status?.enabled === false ? "text-muted" : "text-amber";

  return (
    <SectionCard title="MCP" subtitle="Strategy research server">
      <div className="flex items-center justify-between gap-3 border border-line bg-ink px-3 py-2 text-xs">
        <span className="text-muted">MCP</span>
        <span className={`font-mono ${toneClass}`}>{label}</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <Metric label="Transport" value={status?.transport || "stdio"} />
        <Metric label="Tools" value={status?.tools?.length ?? 0} />
      </div>
      {error || status?.error ? (
        <div className="mt-3 border border-amber/50 bg-amber/10 px-3 py-2 text-xs text-amber">
          {error || status?.error}
        </div>
      ) : null}
    </SectionCard>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="border border-line bg-ink px-2 py-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="mt-1 font-mono text-sm text-text">{String(value ?? "-")}</div>
    </div>
  );
}

function statusLabel(status: MCPStatus | null, isLoading: boolean, error: string | null) {
  if (isLoading) return "Checking";
  if (error || !status) return "Unavailable";
  if (!status.enabled) return "Disabled";
  return status.connected ? "Connected" : "Unavailable";
}

export default memo(MCPStatusPanel);
