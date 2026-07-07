import { useEffect, useState } from "react";
import {
  getMcpToolInventory,
  getSystemDiagnostics,
  getSystemHealth,
  type ApiKeys,
  type McpToolInventory,
  type StrategyRegistrySummary,
  type SystemDiagnostics,
  type SystemHealth,
} from "../../api/client";
import ApiKeyPanel from "../../components/ApiKeyPanel";
import RunInspector from "../runs/RunInspector";

type SystemSettingsProps = {
  apiKeys: ApiKeys;
  onApiKeysChange: (apiKeys: ApiKeys) => void;
  registrySummary: StrategyRegistrySummary | null;
  onSyncRegistry: () => Promise<void>;
  onRefreshRegistry: () => void;
  onRefreshMcp: () => void;
  onRefreshAnalytics: () => void;
};

export default function SystemSettings({
  apiKeys,
  onApiKeysChange,
  registrySummary,
  onSyncRegistry,
  onRefreshRegistry,
  onRefreshMcp,
  onRefreshAnalytics,
}: SystemSettingsProps) {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [tools, setTools] = useState<McpToolInventory | null>(null);
  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null);
  const [langsmithKey, setLangsmithKey] = useState("");
  const [langsmithProject, setLangsmithProject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refreshAll() {
    setBusy(true);
    setError(null);
    try {
      const [healthResponse, toolResponse, diagnosticResponse] = await Promise.all([
        getSystemHealth(),
        getMcpToolInventory(),
        getSystemDiagnostics(),
      ]);
      setHealth(healthResponse);
      setTools(toolResponse);
      setDiagnostics(diagnosticResponse);
    } catch (error) {
      setError(error instanceof Error ? error.message : "System refresh failed.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void refreshAll();
  }, []);

  async function handleSyncRegistry() {
    await onSyncRegistry();
    await refreshAll();
  }

  return (
    <div className="space-y-4">
      <section className="panel-shell p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
          <h2 className="section-title">System / Health / Settings</h2>
          <div className="flex flex-wrap gap-2">
            <button className="terminal-button" type="button" disabled={busy} onClick={() => void refreshAll()}>
              Refresh System
            </button>
            <button className="terminal-button" type="button" onClick={onRefreshMcp}>
              Refresh MCP Health
            </button>
            <button className="terminal-button" type="button" onClick={onRefreshAnalytics}>
              Refresh Analytics Health
            </button>
            <button className="terminal-button terminal-button-green" type="button" disabled={busy} onClick={() => void handleSyncRegistry()}>
              Sync Strategy Registry
            </button>
          </div>
        </div>
        {error ? <div className="border border-red/60 bg-red/10 p-3 text-xs text-red">{error}</div> : null}
        <div className="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="border border-line bg-panel p-4">
              <h3 className="section-title">A. API Keys</h3>
              <div className="mt-3">
                <ApiKeyPanel apiKeys={apiKeys} onChange={onApiKeysChange} />
              </div>
              <div className="mt-4 grid gap-3">
                <label className="space-y-2">
                  <span className="form-label">Optional Tracing Key</span>
                  <input className="form-control font-mono text-xs" type="password" value={langsmithKey} onChange={(event) => setLangsmithKey(event.target.value)} />
                </label>
                <label className="space-y-2">
                  <span className="form-label">Tracing Project</span>
                  <input className="form-control font-mono text-xs" value={langsmithProject} onChange={(event) => setLangsmithProject(event.target.value)} />
                </label>
              </div>
            </div>
            <AdminActions onSyncRegistry={handleSyncRegistry} onRefreshRegistry={onRefreshRegistry} />
          </div>

          <div className="space-y-4">
            <HealthPanel health={health} registrySummary={registrySummary} />
            <ToolInventory tools={tools} />
            <DiagnosticsPanel diagnostics={diagnostics} />
          </div>
        </div>
      </section>
      <RunInspector />
    </div>
  );
}

function HealthPanel({ health, registrySummary }: { health: SystemHealth | null; registrySummary: StrategyRegistrySummary | null }) {
  const rows = [
    ["Backend Health", String(health?.backend?.status || "unknown")],
    ["MCP Health", health?.mcp?.connected ? "connected" : health?.mcp?.enabled === false ? "disabled" : "unknown"],
    ["Analytics DB Health", health?.analytics?.connected ? "connected" : health?.analytics?.enabled === false ? "disabled" : "unknown"],
    ["Metabase Status", String(health?.metabase?.status || "unknown")],
    ["Registry Sync Status", String(health?.registry && !("error" in health.registry) ? "available" : "unknown")],
    ["Last Registry Import", String(registrySummary?.generated_at || "-")],
    ["Imported Strategies", String(registrySummary?.imported_strategies ?? "-")],
    ["Failed Imports", String(registrySummary?.failed_imports ?? "-")],
  ];
  return <KeyValueSection title="B. System Health" rows={rows} />;
}

function ToolInventory({ tools }: { tools: McpToolInventory | null }) {
  return (
    <section className="border border-line bg-panel p-4">
      <h3 className="section-title">C. MCP Tools</h3>
      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <ToolList title="High-Level Public MCP Tools" rows={tools?.public_tools || []} />
        <ToolList title="Legacy MCP Tools" rows={tools?.legacy_tools || []} />
      </div>
    </section>
  );
}

function DiagnosticsPanel({ diagnostics }: { diagnostics: SystemDiagnostics | null }) {
  return (
    <section className="border border-line bg-panel p-4">
      <h3 className="section-title">D. Diagnostics</h3>
      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <JsonBox title="Recent MCP Calls" value={diagnostics?.recent_mcp_calls || []} />
        <JsonBox title="Recent Errors" value={diagnostics?.recent_errors || []} />
        <JsonBox title="Cache Status" value={diagnostics?.cache || {}} />
        <JsonBox title="Artifact / Persistence Status" value={{ artifacts: diagnostics?.artifacts || {}, database: diagnostics?.database || {} }} />
      </div>
    </section>
  );
}

function AdminActions({ onSyncRegistry, onRefreshRegistry }: { onSyncRegistry: () => Promise<void>; onRefreshRegistry: () => void }) {
  return (
    <section className="border border-line bg-panel p-4">
      <h3 className="section-title">E. Admin Actions</h3>
      <div className="mt-3 grid gap-2">
        <button className="terminal-button terminal-button-green" type="button" onClick={() => void onSyncRegistry()}>
          Sync Strategy Registry
        </button>
        <button className="terminal-button" type="button" onClick={onRefreshRegistry}>
          Reload Strategy Catalogue
        </button>
        <button
          className="terminal-button terminal-button-red"
          type="button"
          onClick={() => {
            if (window.confirm("Clear local UI state and reload the application?")) {
              localStorage.removeItem("vectorbt.mcp.apiKeys");
              window.location.reload();
            }
          }}
        >
          Clear Local UI State
        </button>
      </div>
    </section>
  );
}

function KeyValueSection({ title, rows }: { title: string; rows: string[][] }) {
  return (
    <section className="border border-line bg-panel p-4">
      <h3 className="section-title">{title}</h3>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="border border-line bg-ink px-3 py-2">
            <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted">{label}</div>
            <div className="mt-1 break-all font-mono text-xs text-text">{value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ToolList({ title, rows }: { title: string; rows: Array<{ name: string; status: string }> }) {
  return (
    <div className="border border-line bg-ink p-3">
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">{title}</div>
      <div className="max-h-64 overflow-auto">
        {rows.map((row) => (
          <div key={row.name} className="flex justify-between gap-3 border-b border-line/60 py-1 font-mono text-xs">
            <span className="text-text">{row.name}</span>
            <span className={row.status === "available" ? "text-green" : "text-muted"}>{row.status}</span>
          </div>
        ))}
        {!rows.length ? <div className="text-xs text-muted">No tools reported.</div> : null}
      </div>
    </div>
  );
}

function JsonBox({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="border border-line bg-ink p-3">
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">{title}</div>
      <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-muted">{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}
