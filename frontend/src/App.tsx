import { useMemo, useState } from "react";
import { runBacktest, runChat, type BacktestResult, type StrategyName } from "./api/client";
import BacktestForm, { buildBacktestPayload } from "./components/BacktestForm";
import ChatPanel from "./components/ChatPanel";
import ResultDashboard from "./components/ResultDashboard";

const defaultParameters: Record<StrategyName, string> = {
  sma_crossover: JSON.stringify({ fast_window: 20, slow_window: 50 }, null, 2),
  rsi_mean_reversion: JSON.stringify({ rsi_window: 14, lower: 30, upper: 70 }, null, 2),
  bollinger_reversion: JSON.stringify({ window: 20, std_dev: 2 }, null, 2),
};

export default function App() {
  const [symbol, setSymbol] = useState("AAPL");
  const [strategy, setStrategy] = useState<StrategyName>("sma_crossover");
  const [parametersText, setParametersText] = useState(defaultParameters.sma_crossover);
  const [lookback, setLookback] = useState("2y");
  const [monteCarloDays, setMonteCarloDays] = useState(60);
  const [initialCash, setInitialCash] = useState(10000);
  const [fees, setFees] = useState(0.001);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [assistantMessage, setAssistantMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const parseError = useMemo(() => {
    try {
      JSON.parse(parametersText || "{}");
      return null;
    } catch (error) {
      return error instanceof Error ? error.message : "Parameters must be valid JSON.";
    }
  }, [parametersText]);

  function handleStrategyChange(nextStrategy: StrategyName) {
    setStrategy(nextStrategy);
    setParametersText(defaultParameters[nextStrategy]);
  }

  async function handleSubmit() {
    if (parseError) {
      setError("Fix the parameters JSON before running the backtest.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setChatError(null);

    try {
      const payload = buildBacktestPayload(
        symbol,
        strategy,
        parametersText,
        lookback,
        monteCarloDays,
        initialCash,
        fees,
      );
      const response = await runBacktest(payload);
      setResult(response);
      setAssistantMessage(null);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Backtest failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleChatSubmit(message: string) {
    setIsLoading(true);
    setError(null);
    setChatError(null);

    try {
      const response = await runChat(message);
      setAssistantMessage(response.assistant_message || null);

      if (response.status === "needs_input") {
        const message = response.assistant_message || "More input is required.";
        setChatError(message);
        setError(message);
        return;
      }

      if (response.backtest_result) {
        setResult(response.backtest_result);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Chat request failed.";
      setChatError(message);
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-4 text-text lg:px-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-text">VectorBT Strategy Lab</h1>
          <p className="mt-1 text-sm text-muted">Deterministic Finnhub daily-candle backtesting sandbox</p>
        </div>
        <div className="border border-line bg-panel px-3 py-2 text-xs uppercase tracking-[0.14em] text-muted">
          Backend: localhost:8000
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
        <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <BacktestForm
            symbol={symbol}
            strategy={strategy}
            parametersText={parametersText}
            lookback={lookback}
            monteCarloDays={monteCarloDays}
            initialCash={initialCash}
            fees={fees}
            isLoading={isLoading}
            parseError={parseError}
            onSymbolChange={setSymbol}
            onStrategyChange={handleStrategyChange}
            onParametersTextChange={setParametersText}
            onLookbackChange={setLookback}
            onMonteCarloDaysChange={setMonteCarloDays}
            onInitialCashChange={setInitialCash}
            onFeesChange={setFees}
            onSubmit={handleSubmit}
          />
          <ChatPanel
            isLoading={isLoading}
            assistantMessage={assistantMessage}
            error={chatError}
            onSend={handleChatSubmit}
          />
        </aside>

        <section>
          <ResultDashboard result={result} isLoading={isLoading} error={error} />
        </section>
      </div>
    </main>
  );
}
