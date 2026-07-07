import type React from "react";
import type { AnalyticsStatus, MCPStatus, StrategyRegistrySummary } from "../../api/client";
import type { PrimaryTab } from "../tabs";
import StatusBar from "./StatusBar";
import TopTabs from "./TopTabs";

type TerminalShellProps = {
  activeTab: PrimaryTab;
  onTabChange: (tab: PrimaryTab) => void;
  mcpStatus: MCPStatus | null;
  analyticsStatus: AnalyticsStatus | null;
  registrySummary: StrategyRegistrySummary | null;
  children: React.ReactNode;
};

export default function TerminalShell({
  activeTab,
  onTabChange,
  mcpStatus,
  analyticsStatus,
  registrySummary,
  children,
}: TerminalShellProps) {
  return (
    <div className="flex min-h-screen bg-ink text-text">
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="border-b border-line bg-ink px-4 py-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="font-mono text-base font-semibold uppercase tracking-[0.14em] text-text">VectorBT MCP Research Terminal</h1>
              <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.12em] text-muted">MCP-first quant research workspace</div>
            </div>
            <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted">Asia/Tokyo Session</div>
          </div>
        </header>
        <TopTabs activeTab={activeTab} onChange={onTabChange} />
        <main className="min-h-0 flex-1 overflow-auto bg-ink p-4">{children}</main>
        <StatusBar mcpStatus={mcpStatus} analyticsStatus={analyticsStatus} registrySummary={registrySummary} />
      </div>
    </div>
  );
}
