import { useMemo, useState } from "react";
import {
  runChatStream,
  type ApiKeys,
  type ChatResponse,
  type ChatStreamEvent,
  type ResearchResultEnvelope,
} from "../../api/client";
import A2UITemplateRenderer from "../../components/A2UITemplateRenderer";

type AIResearchChatProps = {
  apiKeys: ApiKeys;
  onResult: (envelope: ResearchResultEnvelope | null) => void;
};

type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  runId?: string | null;
};

const examples = [
  "Find executable momentum strategies and backtest AAPL for two years with Monte Carlo.",
  "Run a strategy-conditioned portfolio workflow for AAPL, MSFT, NVDA, and GOOGL using RSI.",
  "Optimize a raw Technology portfolio using max Sharpe and show Monte Carlo risk.",
  "Search for volatility anomaly strategies in OpenAlex and Crossref.",
];

export default function AIResearchChat({ apiKeys, onResult }: AIResearchChatProps) {
  const [input, setInput] = useState(examples[0]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<ChatStreamEvent[]>([]);
  const [lastPrompt, setLastPrompt] = useState("");
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [lastEnvelope, setLastEnvelope] = useState<ResearchResultEnvelope | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const references = useMemo(() => extractReferences(lastResponse, lastEnvelope), [lastEnvelope, lastResponse]);

  async function submit(message: string) {
    const trimmed = message.trim();
    if (!trimmed) return;
    if (!apiKeys.chatApiKey.trim()) {
      setError("Chat API key is required for AI Research Chat.");
      return;
    }
    setBusy(true);
    setError(null);
    setEvents([]);
    setLastPrompt(trimmed);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    try {
      let assistantDraft = "";
      const response = await runChatStream(trimmed, apiKeys, (event) => {
        setEvents((current) => [...current.slice(-99), event]);
        if (event.event === "message.delta" && typeof event.data.content === "string") {
          assistantDraft = String(event.data.content);
        }
      });
      const envelope = envelopeFromChatResponse(response);
      setLastResponse(response);
      setLastEnvelope(envelope);
      onResult(envelope);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.assistant_message || assistantDraft || "Workflow completed.",
          runId: envelope?.run_id || null,
        },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Chat stream failed.";
      setError(message);
      setMessages((current) => [...current, { role: "system", content: message }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid h-[calc(100vh-168px)] min-h-[680px] grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_390px]">
      <section className="panel-shell flex min-h-0 flex-col">
        <div className="border-b border-line p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="section-title">AI Research Chat</h2>
              <div className="mt-2 font-mono text-xs text-muted">Streaming research workspace with MCP workflow events and A2UI results.</div>
            </div>
            <div className="flex gap-2">
              <button className="terminal-button" type="button" disabled={busy || !lastPrompt} onClick={() => void submit(lastPrompt)}>
                Retry
              </button>
              <button
                className="terminal-button"
                type="button"
                disabled={busy}
                onClick={() => {
                  setMessages([]);
                  setEvents([]);
                  setLastResponse(null);
                  setLastEnvelope(null);
                  setError(null);
                  onResult(null);
                }}
              >
                Clear
              </button>
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-4">
          <div className="space-y-3">
            {messages.length ? (
              messages.map((message, index) => <MessageBubble key={index} message={message} />)
            ) : (
              <div className="border border-dashed border-line bg-ink p-6 text-sm leading-6 text-muted">
                Ask for strategy search, backtests, strategy-conditioned optimization, raw Markowitz, Monte Carlo, discovery, or prior run inspection.
              </div>
            )}
          </div>

          {error ? (
            <div className="mt-4 border border-red/60 bg-red/10 p-3 text-sm leading-6 text-red">
              <div className="mb-2 font-mono text-xs uppercase tracking-[0.12em]">Error</div>
              {error}
              <button className="ml-3 border border-red/50 px-2 py-1 text-xs" type="button" onClick={() => setError(null)}>
                Clear Error
              </button>
            </div>
          ) : null}

          {lastEnvelope ? (
            <div className="mt-4">
              <A2UITemplateRenderer envelope={lastEnvelope} />
            </div>
          ) : null}
        </div>

        <form
          className="border-t border-line p-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit(input);
          }}
        >
          <textarea
            className="form-control min-h-24 resize-y text-sm leading-6"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Run a strategy-conditioned Markowitz workflow for AAPL, MSFT, NVDA using RSI..."
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {examples.map((example) => (
                <button key={example} className="terminal-button px-2 py-1 text-[11px]" type="button" onClick={() => setInput(example)}>
                  {example.slice(0, 28)}
                </button>
              ))}
            </div>
            <button className="terminal-button terminal-button-green px-5" type="submit" disabled={busy || !input.trim()}>
              {busy ? "Streaming" : "Send"}
            </button>
          </div>
        </form>
      </section>

      <aside className="grid min-h-0 gap-4 xl:grid-rows-[minmax(0,1fr)_260px]">
        <section className="panel-shell min-h-0 overflow-hidden">
          <div className="border-b border-line p-4">
            <h3 className="section-title">Event / Progress Log</h3>
          </div>
          <div className="h-full overflow-auto p-3 font-mono text-[11px] leading-5">
            {events.length ? events.map((event, index) => <EventRow key={`${event.event}-${index}`} event={event} />) : <div className="text-muted">No stream events.</div>}
          </div>
        </section>

        <section className="panel-shell overflow-auto p-4">
          <h3 className="section-title">Linked References</h3>
          <div className="mt-3 space-y-2 font-mono text-xs">
            {references.length ? references.map((item) => <ReferenceRow key={`${item.label}-${item.value}`} label={item.label} value={item.value} />) : <div className="text-muted">No run, strategy, or artifact references yet.</div>}
          </div>
        </section>
      </aside>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const tone = message.role === "system" ? "border-red/60 bg-red/10 text-red" : isUser ? "border-muted/40 bg-panel2 text-text" : "border-green/40 bg-green/10 text-text";
  return (
    <div className={`max-w-4xl border p-3 text-sm leading-6 ${tone}`}>
      <div className="mb-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
        {message.role}
        {message.runId ? ` / ${message.runId}` : ""}
      </div>
      {message.content}
    </div>
  );
}

function EventRow({ event }: { event: ChatStreamEvent }) {
  return (
    <div className="grid grid-cols-[138px_minmax(0,1fr)] gap-2 border-b border-line/70 py-1">
      <span className="text-green">{event.event}</span>
      <span className="truncate text-muted">{eventSummary(event.data)}</span>
    </div>
  );
}

function ReferenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border border-line bg-ink px-3 py-2">
      <span className="text-muted">{label}</span>
      <span className="break-all text-right text-green">{value}</span>
    </div>
  );
}

function eventSummary(data: Record<string, unknown>): string {
  if (typeof data.content === "string") return data.content;
  if (typeof data.tool === "string") return data.tool;
  if (typeof data.run_id === "string") return data.run_id;
  if (typeof data.result_type === "string") return data.result_type;
  if (typeof data.message === "string") return data.message;
  return JSON.stringify(data);
}

function envelopeFromChatResponse(response: ChatResponse): ResearchResultEnvelope | null {
  if (response.portfolio_result) {
    return {
      status: response.status,
      workflow_type: "portfolio_optimization",
      run_id: response.portfolio_result.artifact_id || null,
      strategy: { name: "Portfolio Optimization" },
      universe: { symbols: response.portfolio_result.symbols_used || response.portfolio_result.symbols || [], sector: response.portfolio_result.sector },
      parameters: objectValue(response.parsed_request) || {},
      metrics: response.portfolio_result.metrics || {},
      allocations: { weights: response.portfolio_result.weights || {} },
      frontier: response.portfolio_result.charts?.efficient_frontier || [],
      warnings: response.warnings || response.portfolio_result.warnings || [],
      artifacts: response.portfolio_result.artifact_url
        ? [{ artifact_id: response.portfolio_result.artifact_id || "portfolio", artifact_url: response.portfolio_result.artifact_url, artifact_type: "json", summary: {} }]
        : [],
      ui_hint: "optimized_multi_stock_portfolio",
    };
  }
  if (response.backtest_result) {
    return {
      status: response.status,
      workflow_type: "strategy_backtest",
      run_id: stringValue(response.backtest_result.diagnostics?.mcp && (response.backtest_result.diagnostics.mcp as Record<string, unknown>).run_id),
      strategy: { name: response.backtest_result.request?.strategy || "Strategy Backtest" },
      universe: { symbols: response.backtest_result.request?.symbol ? [response.backtest_result.request.symbol] : [] },
      parameters: response.backtest_result.request?.parameters || {},
      metrics: response.backtest_result.metrics || {},
      summary: response.backtest_result.summary || {},
      trades: response.backtest_result.tables?.trades || [],
      equity: response.backtest_result.charts?.equity_curve || [],
      drawdown: response.backtest_result.charts?.drawdown_curve || [],
      warnings: response.backtest_result.warnings || response.warnings || [],
      errors: response.backtest_result.errors || [],
      ui_hint: "single_stock_research",
    };
  }
  return null;
}

function extractReferences(response: ChatResponse | null, envelope: ResearchResultEnvelope | null): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];
  if (envelope?.run_id) rows.push({ label: "Run ID", value: envelope.run_id });
  const strategy = objectValue(envelope?.strategy);
  if (strategy?.strategy_id) rows.push({ label: "Strategy", value: String(strategy.strategy_id) });
  if (strategy?.name) rows.push({ label: "Strategy Name", value: String(strategy.name) });
  for (const artifact of envelope?.artifacts || []) {
    if (artifact.artifact_url) rows.push({ label: "Artifact", value: String(artifact.artifact_url) });
    else if (artifact.artifact_id) rows.push({ label: "Artifact", value: String(artifact.artifact_id) });
  }
  const parsed = objectValue(response?.parsed_request);
  if (parsed?.strategy_id) rows.push({ label: "Parsed Strategy", value: String(parsed.strategy_id) });
  if (parsed?.strategy) rows.push({ label: "Parsed Strategy", value: String(parsed.strategy) });
  return rows;
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}
