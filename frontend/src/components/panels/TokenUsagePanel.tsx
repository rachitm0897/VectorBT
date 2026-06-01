import { memo } from "react";
import SectionCard from "../layout/SectionCard";

type TokenUsagePanelProps = {
  diagnostics?: Record<string, unknown> | null;
  usedChat?: boolean;
};

function TokenUsagePanel({ diagnostics, usedChat }: TokenUsagePanelProps) {
  return (
    <SectionCard title="Token / Cache" subtitle="Parser-only AI budget">
      <div className="grid grid-cols-2 gap-2 text-xs">
        <TokenMetric label="LLM Calls" value={diagnostics?.llm_calls ?? (usedChat ? "0-1" : 0)} />
        <TokenMetric label="Parser Cache" value={diagnostics?.parser_cache ?? "unknown"} />
        <TokenMetric label="Prompt Tokens" value={diagnostics?.estimated_prompt_tokens ?? "-"} />
        <TokenMetric label="Output Tokens" value={diagnostics?.estimated_output_tokens ?? "-"} />
      </div>
      <p className="mt-3 border-t border-line pt-3 text-xs leading-5 text-muted">
        Chat uses one parser call on cache miss. Response narration is a Python template; market data and backtest arrays stay
        out of the LLM context.
      </p>
    </SectionCard>
  );
}

function TokenMetric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="border border-line bg-ink px-2 py-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="mt-1 font-mono text-sm text-text">{String(value ?? "-")}</div>
    </div>
  );
}

export default memo(TokenUsagePanel);
