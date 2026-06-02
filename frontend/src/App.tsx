import { useEffect, useMemo, useState } from "react";
import {
  fetchAnalyticsStatus,
  fetchMCPStatus,
  runBacktest,
  runChat,
  type AnalyticsStatus,
  type BacktestRequest,
  type BacktestResult,
  type MCPStatus,
  type StrategyName,
} from "./api/client";
import BacktestForm, { buildBacktestPayload } from "./components/BacktestForm";
import ChatPanel from "./components/ChatPanel";
import AppShell from "./components/layout/AppShell";
import Sidebar from "./components/layout/Sidebar";
import AnalyticsStatusPanel from "./components/panels/AnalyticsStatusPanel";
import MCPStatusPanel from "./components/panels/MCPStatusPanel";
import ParsedRequestPanel from "./components/panels/ParsedRequestPanel";
import TokenUsagePanel from "./components/panels/TokenUsagePanel";
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
  const [parsedRequest, setParsedRequest] = useState<BacktestRequest | Record<string, unknown> | null>(null);
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown> | null>(null);
  const [usedChat, setUsedChat] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [analyticsStatus, setAnalyticsStatus] = useState<AnalyticsStatus | null>(null);
  const [analyticsStatusError, setAnalyticsStatusError] = useState<string | null>(null);
  const [isAnalyticsStatusLoading, setIsAnalyticsStatusLoading] = useState(true);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [mcpStatusError, setMcpStatusError] = useState<string | null>(null);
  const [isMcpStatusLoading, setIsMcpStatusLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    fetchMCPStatus()
      .then((status) => {
        if (!isMounted) return;
        setMcpStatus(status);
        setMcpStatusError(null);
      })
      .catch((error) => {
        if (!isMounted) return;
        setMcpStatus(null);
        setMcpStatusError(error instanceof Error ? error.message : "MCP status unavailable.");
      })
      .finally(() => {
        if (isMounted) {
          setIsMcpStatusLoading(false);
        }
      });

    fetchAnalyticsStatus()
      .then((status) => {
        if (!isMounted) return;
        setAnalyticsStatus(status);
        setAnalyticsStatusError(null);
      })
      .catch((error) => {
        if (!isMounted) return;
        setAnalyticsStatus(null);
        setAnalyticsStatusError(error instanceof Error ? error.message : "Analytics status unavailable.");
      })
      .finally(() => {
        if (isMounted) {
          setIsAnalyticsStatusLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

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
      setParsedRequest(payload);
      setDiagnostics(response.diagnostics || null);
      setUsedChat(false);
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
      setParsedRequest(response.parsed_request || null);
      setDiagnostics(response.diagnostics || response.backtest_result?.diagnostics || null);
      setUsedChat(true);

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
    <AppShell
      sidebar={
        <Sidebar>
          <ChatPanel
            isLoading={isLoading}
            assistantMessage={assistantMessage}
            error={chatError}
            onSend={handleChatSubmit}
          />
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
          <ParsedRequestPanel parsedRequest={parsedRequest} result={result} />
          <TokenUsagePanel diagnostics={diagnostics || result?.diagnostics} usedChat={usedChat} />
          <MCPStatusPanel
            status={mcpStatus}
            isLoading={isMcpStatusLoading}
            error={mcpStatusError}
          />
          <AnalyticsStatusPanel
            status={analyticsStatus}
            isLoading={isAnalyticsStatusLoading}
            error={analyticsStatusError}
          />
        </Sidebar>
      }
    >
      <ResultDashboard
        result={result}
        isLoading={isLoading}
        error={error}
        parsedRequest={parsedRequest}
        diagnostics={diagnostics}
        usedChat={usedChat}
      />
    </AppShell>
  );
}
