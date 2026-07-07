import { useEffect, useMemo, useState } from "react";
import {
  fetchStrategyDetails,
  type MultiStockResearchRequest,
  type SingleStockResearchRequest,
  type StrategyDetails,
  type StrategyRegistryItem,
} from "../api/client";

type ManualResearchLabProps = {
  strategies: StrategyRegistryItem[];
  isLoading: boolean;
  onRunSingle: (payload: SingleStockResearchRequest) => Promise<void>;
  onRunMulti: (payload: MultiStockResearchRequest) => Promise<void>;
};

type Mode = "single" | "multi";

export default function ManualResearchLab({
  strategies,
  isLoading,
  onRunSingle,
  onRunMulti,
}: ManualResearchLabProps) {
  const executableStrategies = useMemo(
    () =>
      strategies.filter(
        (strategy) => strategy.runnable && strategy.execution_type === "single_asset_signal",
      ),
    [strategies],
  );
  const [mode, setMode] = useState<Mode>("single");
  const [symbol, setSymbol] = useState("AAPL");
  const [symbolsText, setSymbolsText] = useState("AAPL, MSFT, NVDA, GOOGL");
  const [strategyId, setStrategyId] = useState("");
  const [strategyDetails, setStrategyDetails] = useState<StrategyDetails | null>(null);
  const [parametersText, setParametersText] = useState("{}");
  const [optimizationText, setOptimizationText] = useState(
    JSON.stringify(
      {
        objective: "max_sharpe",
        long_only: true,
        max_weight: 0.6,
        covariance_regularization: 0.000001,
      },
      null,
      2,
    ),
  );
  const [lookback, setLookback] = useState<"1mo" | "6mo" | "1y" | "2y" | "5y">("2y");
  const [initialCash, setInitialCash] = useState(10000);
  const [fees, setFees] = useState(0.001);
  const [monteCarloDays, setMonteCarloDays] = useState(60);
  const [simulations, setSimulations] = useState(500);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!strategyId && executableStrategies.length) {
      setStrategyId(executableStrategies[0].strategy_id);
    }
  }, [executableStrategies, strategyId]);

  useEffect(() => {
    if (!strategyId) return;
    let cancelled = false;
    fetchStrategyDetails(strategyId)
      .then((response) => {
        if (cancelled) return;
        const details = response.strategy || null;
        setStrategyDetails(details);
        setParametersText(JSON.stringify(details?.default_parameters || {}, null, 2));
      })
      .catch((error) => {
        if (cancelled) return;
        setLocalError(error instanceof Error ? error.message : "Could not load strategy details.");
      });
    return () => {
      cancelled = true;
    };
  }, [strategyId]);

  const parameterError = useMemo(() => parseJsonError(parametersText), [parametersText]);
  const optimizationError = useMemo(() => parseJsonError(optimizationText), [optimizationText]);
  const selectedStrategy = executableStrategies.find((strategy) => strategy.strategy_id === strategyId);

  async function handleSubmit() {
    setLocalError(null);
    if (!strategyId) {
      setLocalError("Select a runnable strategy.");
      return;
    }
    if (parameterError || (mode === "multi" && optimizationError)) {
      setLocalError("Fix JSON fields before running research.");
      return;
    }
    const parameters = JSON.parse(parametersText || "{}") as Record<string, unknown>;
    if (mode === "single") {
      await onRunSingle({
        symbol: symbol.trim().toUpperCase(),
        strategy_id: strategyId,
        parameters,
        lookback,
        resolution: "D",
        initial_cash: initialCash,
        fees,
        monte_carlo: {
          enabled: true,
          days: monteCarloDays,
          simulations,
          mode: "strategy_returns",
        },
      });
      return;
    }
    await onRunMulti({
      symbols: parseSymbols(symbolsText),
      strategy_id: strategyId,
      parameters,
      lookback,
      resolution: "D",
      initial_cash: initialCash,
      fees,
      optimization: JSON.parse(optimizationText || "{}") as Record<string, unknown>,
      monte_carlo: {
        enabled: true,
        days: monteCarloDays,
        simulations,
        mode: "portfolio_returns",
      },
    });
  }

  return (
    <section className="panel-shell p-4">
      <div className="mb-3 flex items-center justify-between border-b border-line pb-3">
        <h2 className="section-title">Manual Research Lab</h2>
        <span className="border border-line px-2 py-1 font-mono text-[11px] text-muted">
          {executableStrategies.length} runnable
        </span>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2">
        <ModeButton active={mode === "single"} onClick={() => setMode("single")}>
          Single Stock
        </ModeButton>
        <ModeButton active={mode === "multi"} onClick={() => setMode("multi")}>
          Multi Stock
        </ModeButton>
      </div>

      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void handleSubmit();
        }}
      >
        {mode === "single" ? (
          <label className="space-y-2">
            <span className="form-label">Symbol</span>
            <input className="form-control font-mono" value={symbol} onChange={(event) => setSymbol(event.target.value)} />
          </label>
        ) : (
          <label className="space-y-2">
            <span className="form-label">Symbols</span>
            <textarea
              className="form-control min-h-20 resize-y font-mono text-xs"
              value={symbolsText}
              onChange={(event) => setSymbolsText(event.target.value)}
            />
          </label>
        )}

        <label className="space-y-2">
          <span className="form-label">Strategy Registry</span>
          <select className="form-control" value={strategyId} onChange={(event) => setStrategyId(event.target.value)}>
            {executableStrategies.map((strategy) => (
              <option key={strategy.strategy_id} value={strategy.strategy_id}>
                {strategy.name} / {strategy.strategy_id}
              </option>
            ))}
          </select>
        </label>

        {selectedStrategy ? (
          <div className="border border-line bg-ink p-3 text-xs leading-5 text-muted">
            <div className="font-mono text-text">{selectedStrategy.readiness} / {selectedStrategy.execution_type}</div>
            <div>{selectedStrategy.description || strategyDetails?.description}</div>
          </div>
        ) : null}

        <div className="grid grid-cols-3 gap-3">
          <label className="space-y-2">
            <span className="form-label">Lookback</span>
            <select className="form-control" value={lookback} onChange={(event) => setLookback(event.target.value as typeof lookback)}>
              {["1mo", "6mo", "1y", "2y", "5y"].map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label className="space-y-2">
            <span className="form-label">Cash</span>
            <input className="form-control" type="number" min={1} value={initialCash} onChange={(event) => setInitialCash(Number(event.target.value))} />
          </label>
          <label className="space-y-2">
            <span className="form-label">Fees</span>
            <input className="form-control" type="number" min={0} step={0.0005} value={fees} onChange={(event) => setFees(Number(event.target.value))} />
          </label>
        </div>

        <label className="space-y-2">
          <span className="form-label">Parameters JSON</span>
          <textarea
            className="form-control min-h-32 resize-y font-mono text-xs leading-5"
            value={parametersText}
            onChange={(event) => setParametersText(event.target.value)}
            spellCheck={false}
          />
        </label>
        {parameterError ? <ErrorLine message={parameterError} /> : null}

        {mode === "multi" ? (
          <label className="space-y-2">
            <span className="form-label">Optimization JSON</span>
            <textarea
              className="form-control min-h-36 resize-y font-mono text-xs leading-5"
              value={optimizationText}
              onChange={(event) => setOptimizationText(event.target.value)}
              spellCheck={false}
            />
          </label>
        ) : null}
        {mode === "multi" && optimizationError ? <ErrorLine message={optimizationError} /> : null}

        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-2">
            <span className="form-label">MC Days</span>
            <input className="form-control" type="number" min={1} max={365} value={monteCarloDays} onChange={(event) => setMonteCarloDays(Number(event.target.value))} />
          </label>
          <label className="space-y-2">
            <span className="form-label">Simulations</span>
            <input className="form-control" type="number" min={100} max={5000} value={simulations} onChange={(event) => setSimulations(Number(event.target.value))} />
          </label>
        </div>

        {localError ? <ErrorLine message={localError} /> : null}

        <button
          className="w-full border border-green bg-green/15 px-4 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-green transition hover:bg-green/25 disabled:cursor-not-allowed disabled:border-line disabled:bg-line/30 disabled:text-muted"
          type="submit"
          disabled={isLoading || !strategyId}
        >
          {isLoading ? "Running Research" : "Run Research"}
        </button>
      </form>
    </section>
  );
}

function ModeButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button
      className={`border px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${
        active ? "border-green bg-green/15 text-green" : "border-line bg-ink text-muted hover:border-green"
      }`}
      type="button"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function ErrorLine({ message }: { message: string }) {
  return <div className="border border-red/60 bg-red/10 px-3 py-2 text-xs text-red">{message}</div>;
}

function parseSymbols(value: string): string[] {
  return value
    .split(/[\s,;]+/)
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean)
    .filter((symbol, index, symbols) => symbols.indexOf(symbol) === index);
}

function parseJsonError(value: string): string | null {
  try {
    JSON.parse(value || "{}");
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : "Invalid JSON.";
  }
}
