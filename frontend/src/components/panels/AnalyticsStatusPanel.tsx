import type { AnalyticsStatus } from "../../api/client";

type AnalyticsStatusPanelProps = {
  status: AnalyticsStatus | null;
  isLoading: boolean;
  error: string | null;
  metabaseUrl: string;
  onRefresh: () => void;
};

export default function AnalyticsStatusPanel({
  status,
  isLoading,
  error,
  metabaseUrl,
  onRefresh,
}: AnalyticsStatusPanelProps) {
  const state = connectionState(status, isLoading, error);

  function openMetabase() {
    window.open(metabaseUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <button
          className="border border-cyan bg-cyan/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-cyan transition hover:bg-cyan/15"
          type="button"
          onClick={openMetabase}
        >
          Metabase Analytics
        </button>
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
        <span className="text-[10px] uppercase tracking-[0.14em] text-muted">Analytics DB</span>
        <span className={`text-xs font-semibold uppercase tracking-[0.14em] ${state.className}`}>{state.label}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <StatusCell label="Enabled" value={formatBoolean(status?.enabled)} />
        <StatusCell label="Connected" value={formatBoolean(status?.connected)} />
        <StatusCell label="Database" value={status?.database || "-"} />
        <StatusCell label="Host" value={status?.host || "-"} />
      </div>

      <StatusLine label="Metabase URL" value={status?.metabase_url || metabaseUrl} />
      {error || status?.error ? <Message value={error || status?.error || "Analytics status check failed."} /> : null}
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

function connectionState(status: AnalyticsStatus | null, isLoading: boolean, error: string | null) {
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
