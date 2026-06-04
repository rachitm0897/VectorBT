import { useState } from "react";

type ChatPanelProps = {
  isLoading: boolean;
  assistantMessage: string | null;
  error: string | null;
  onSend: (message: string) => Promise<void>;
};

const examples = [
  {
    title: "Strategy backtest",
    prompt: "Backtest AAPL using RSI. Buy below 30 and sell above 70. Run Monte Carlo for 60 days.",
  },
  {
    title: "Symbol Markowitz",
    prompt: "Optimize AAPL, MSFT, NVDA and GOOGL using Markowitz.",
  },
  {
    title: "Technology Markowitz",
    prompt: "Create a max Sharpe portfolio from Technology stocks using Markowitz.",
  },
  {
    title: "Healthcare Min Vol",
    prompt: "Find a minimum volatility portfolio from Healthcare stocks using Markowitz.",
  },
];

export default function ChatPanel({ isLoading, assistantMessage, error, onSend }: ChatPanelProps) {
  const [message, setMessage] = useState(examples[0].prompt);

  return (
    <section className="panel-shell p-4">
      <div className="mb-3 flex items-center justify-between border-b border-line pb-3">
        <h2 className="section-title">AI Parser Chat</h2>
        <span className="border border-line px-2 py-1 text-[11px] uppercase tracking-[0.14em] text-muted">
          One LLM Call
        </span>
      </div>

      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void onSend(message);
        }}
      >
        <label className="space-y-2">
          <span className="form-label">Natural Language Request</span>
          <textarea
            className="form-control min-h-28 resize-y text-sm leading-6"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Backtest AAPL using RSI below 30 and sell above 70 for 2 years"
          />
        </label>

        <button
          className="w-full border border-green bg-green/15 px-4 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-green transition hover:bg-green/25 disabled:cursor-not-allowed disabled:border-line disabled:bg-line/30 disabled:text-muted"
          type="submit"
          disabled={isLoading || !message.trim()}
        >
          {isLoading ? "Parsing And Running" : "Run From Chat"}
        </button>
      </form>

      <div className="mt-4 space-y-2">
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Examples</div>
        {examples.map((example) => (
          <button
            key={example.title}
            className="block w-full border border-line bg-ink px-3 py-2 text-left text-xs leading-5 text-muted transition hover:border-cyan hover:text-text"
            type="button"
            onClick={() => setMessage(example.prompt)}
          >
            <span className="mb-1 block font-semibold uppercase tracking-[0.12em] text-cyan">{example.title}</span>
            {example.prompt}
          </button>
        ))}
      </div>

      {assistantMessage ? (
        <div className="mt-4 border border-green/50 bg-green/10 p-3 text-sm leading-6 text-text">{assistantMessage}</div>
      ) : null}

      {error ? <div className="mt-4 border border-red/60 bg-red/10 p-3 text-sm leading-6 text-red">{error}</div> : null}

      <div className="mt-4 border border-dashed border-line bg-ink p-3 text-xs leading-5 text-muted">
        The LLM only parses the message into JSON. Market data, trades, equity curves, and Monte Carlo paths stay inside
        the deterministic backend.
      </div>
    </section>
  );
}
