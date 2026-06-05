import type { BacktestRequest, StrategyName } from "../api/client";

type BacktestFormProps = {
  symbol: string;
  strategy: StrategyName;
  parametersText: string;
  lookback: string;
  monteCarloDays: number;
  initialCash: number;
  fees: number;
  isLoading: boolean;
  parseError: string | null;
  onSymbolChange: (value: string) => void;
  onStrategyChange: (value: StrategyName) => void;
  onParametersTextChange: (value: string) => void;
  onLookbackChange: (value: string) => void;
  onMonteCarloDaysChange: (value: number) => void;
  onInitialCashChange: (value: number) => void;
  onFeesChange: (value: number) => void;
  onSubmit: () => void;
};

const strategyLabels: Record<StrategyName, string> = {
  sma_crossover: "SMA crossover",
  rsi_mean_reversion: "RSI mean reversion",
  bollinger_reversion: "Bollinger reversion",
  macd_crossover: "MACD crossover",
};

export function buildBacktestPayload(
  symbol: string,
  strategy: StrategyName,
  parametersText: string,
  lookback: string,
  monteCarloDays: number,
  initialCash: number,
  fees: number,
): BacktestRequest {
  return {
    symbol,
    strategy,
    parameters: JSON.parse(parametersText || "{}"),
    lookback,
    resolution: "D",
    initial_cash: initialCash,
    fees,
    monte_carlo: {
      enabled: true,
      days: monteCarloDays,
      simulations: 500,
      method: "bootstrap",
    },
  };
}

export default function BacktestForm({
  symbol,
  strategy,
  parametersText,
  lookback,
  monteCarloDays,
  initialCash,
  fees,
  isLoading,
  parseError,
  onSymbolChange,
  onStrategyChange,
  onParametersTextChange,
  onLookbackChange,
  onMonteCarloDaysChange,
  onInitialCashChange,
  onFeesChange,
  onSubmit,
}: BacktestFormProps) {
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-2">
            <span className="form-label">Symbol</span>
            <input
              className="form-control"
              value={symbol}
              onChange={(event) => onSymbolChange(event.target.value)}
              placeholder="AAPL"
            />
          </label>

          <label className="space-y-2">
            <span className="form-label">Lookback</span>
            <input
              className="form-control"
              value={lookback}
              onChange={(event) => onLookbackChange(event.target.value)}
              placeholder="2y"
            />
          </label>
        </div>

        <label className="space-y-2">
          <span className="form-label">Strategy</span>
          <select
            className="form-control"
            value={strategy}
            onChange={(event) => onStrategyChange(event.target.value as StrategyName)}
          >
            {Object.entries(strategyLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2">
          <span className="form-label">Parameters JSON</span>
          <textarea
            className="form-control min-h-36 resize-y font-mono text-xs leading-5"
            value={parametersText}
            onChange={(event) => onParametersTextChange(event.target.value)}
            spellCheck={false}
          />
        </label>

        {parseError ? (
          <div className="border border-red/60 bg-red/10 px-3 py-2 text-sm text-red">{parseError}</div>
        ) : null}

        <div className="grid grid-cols-3 gap-3">
          <label className="space-y-2">
            <span className="form-label">MC Days</span>
            <input
              className="form-control"
              type="number"
              min={1}
              max={365}
              value={monteCarloDays}
              onChange={(event) => onMonteCarloDaysChange(Number(event.target.value))}
            />
          </label>

          <label className="space-y-2">
            <span className="form-label">Cash</span>
            <input
              className="form-control"
              type="number"
              min={1}
              value={initialCash}
              onChange={(event) => onInitialCashChange(Number(event.target.value))}
            />
          </label>

          <label className="space-y-2">
            <span className="form-label">Fees</span>
            <input
              className="form-control"
              type="number"
              min={0}
              step={0.0005}
              value={fees}
              onChange={(event) => onFeesChange(Number(event.target.value))}
            />
          </label>
        </div>

        <button
          className="w-full border border-cyan bg-cyan/15 px-4 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-cyan transition hover:bg-cyan/25 disabled:cursor-not-allowed disabled:border-line disabled:bg-line/30 disabled:text-muted"
          type="submit"
          disabled={isLoading}
        >
          {isLoading ? "Running Backtest" : "Run Backtest"}
        </button>
    </form>
  );
}
