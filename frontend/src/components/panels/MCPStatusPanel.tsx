import type { BacktestResult, MCPStatus } from "../../api/client";

type McpStatusPanelProps = {
  status: MCPStatus | null;
  isLoading: boolean;
  error: string | null;
  diagnostics?: Record<string, unknown> | null;
  result?: BacktestResult | null;
  onRefresh: () => void;
};

export default function McpStatusPanel({
  status,
  isLoading,
  error,
  diagnostics,
  result,
  onRefresh,
}: McpStatusPanelProps) {
  const mcpDiagnostics = readMcpDiagnostics(diagnostics || result?.diagnostics || null);
  const state = connectionState(status, isLoading, error);
  const toolCount = status?.tools?.length || 0;
  const usesResearchTool = Boolean(status?.tools?.includes("run_strategy_research"));
  const hasOptimizerTool = Boolean(status?.tools?.includes("run_markowitz_optimization"));
  const lastRunUsedMcp = Boolean(mcpDiagnostics?.enabled);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs leading-5 text-muted">Remote financial tools and latest execution diagnostics.</span>
        <button
          className="border border-line px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted transition hover:border-cyan hover:text-cyan disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
        >
          {isLoading ? "Checking" : "Refresh"}
        </button>
      </div>

      <div className="flex items-center justify-between border border-line bg-ink px-3 py-2">
        <span className="text-[10px] uppercase tracking-[0.14em] text-muted">Connection</span>
        <span className={`text-xs font-semibold uppercase tracking-[0.14em] ${state.className}`}>{state.label}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <StatusCell label="Enabled" value={formatBoolean(status?.enabled)} />
        <StatusCell label="Transport" value={status?.transport || "-"} />
        <StatusCell label="Tools" value={toolCount ? String(toolCount) : "-"} />
        <StatusCell label="Research Tool" value={usesResearchTool ? "Available" : "Missing"} />
        <StatusCell label="Optimizer" value={hasOptimizerTool ? "Available" : "Missing"} />
      </div>

      <StatusLine label="Server URL" value={status?.server_url || "-"} />
      {error || status?.error ? <Message value={error || status?.error || "MCP status check failed."} /> : null}

      <div className="mt-3 border-t border-line pt-3">
        <div className="mb-2 text-[10px] uppercase tracking-[0.14em] text-muted">Latest Run</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <StatusCell label="Executor" value={lastRunUsedMcp ? "MCP" : "Not reported"} />
          <StatusCell label="Tool" value={asString(mcpDiagnostics?.tool) || "-"} />
          <StatusCell label="Run ID" value={asString(mcpDiagnostics?.run_id) || "-"} />
          <StatusCell label="Artifact" value={asString(mcpDiagnostics?.artifact_id) || "-"} />
        </div>
        {mcpDiagnostics?.artifact_url ? <StatusLine label="Artifact URL" value={asString(mcpDiagnostics.artifact_url)} /> : null}
      </div>
    </div>
  );
}

function StatusCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border border-line bg-ink px-3 py-2">
      <div className="truncate text-[10px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="mt-1 truncate font-mono text-text" title={value}>
        {value}
      </div>
    </div>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-2 min-w-0 border border-line bg-ink px-3 py-2 text-xs">
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="mt-1 break-all font-mono text-text">{value}</div>
    </div>
  );
}

function Message({ value }: { value: string }) {
  return <div className="mt-3 border border-red/60 bg-red/10 px-3 py-2 text-xs leading-5 text-red">{value}</div>;
}

function readMcpDiagnostics(diagnostics: Record<string, unknown> | null): Record<string, unknown> | null {
  const value = diagnostics?.mcp;
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function connectionState(status: MCPStatus | null, isLoading: boolean, error: string | null) {
  if (isLoading) {
    return { label: "Checking", className: "text-amber" };
  }
  if (error) {
    return { label: "Error", className: "text-red" };
  }
  if (!status) {
    return { label: "Unknown", className: "text-muted" };
  }
  if (!status.enabled) {
    return { label: "Disabled", className: "text-muted" };
  }
  if (status.connected) {
    return { label: "Connected", className: "text-green" };
  }
  return { label: "Offline", className: "text-red" };
}

function formatBoolean(value: boolean | undefined): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "-";
}

function asString(value: unknown): string {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : "";
}
