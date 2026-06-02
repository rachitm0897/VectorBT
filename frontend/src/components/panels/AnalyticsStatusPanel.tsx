import { memo } from "react";
import type { AnalyticsStatus } from "../../api/client";
import SectionCard from "../layout/SectionCard";

type AnalyticsStatusPanelProps = {
  status: AnalyticsStatus | null;
  isLoading: boolean;
  error: string | null;
};

function AnalyticsStatusPanel({ status, isLoading, error }: AnalyticsStatusPanelProps) {
  const metabaseUrl = status?.metabase_url || "http://localhost:3000";
  const label = statusLabel(status, isLoading, error);
  const toneClass = status?.enabled && status.connected ? "text-green" : status?.enabled === false ? "text-muted" : "text-amber";

  return (
    <SectionCard title="Analytics" subtitle="Metabase reporting layer">
      <div className="flex items-center justify-between gap-3 border border-line bg-ink px-3 py-2 text-xs">
        <span className="text-muted">Analytics</span>
        <span className={`font-mono ${toneClass}`}>{label}</span>
      </div>
      <a
        className="mt-3 block border border-cyan/60 bg-cyan/10 px-3 py-2 text-center text-xs font-semibold uppercase tracking-[0.12em] text-cyan transition hover:bg-cyan/15"
        href={metabaseUrl}
        rel="noreferrer"
        target="_blank"
      >
        Open Metabase Analytics
      </a>
    </SectionCard>
  );
}

function statusLabel(status: AnalyticsStatus | null, isLoading: boolean, error: string | null) {
  if (isLoading) return "Checking";
  if (error || !status) return "Unavailable";
  if (!status.enabled) return "Disabled";
  return status.connected ? "Connected" : "Unavailable";
}

export default memo(AnalyticsStatusPanel);

