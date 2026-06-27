import { useCallback, useEffect, useMemo, useState } from "react";
import {
  DEFAULT_CHAT_MODEL,
  DEFAULT_CHAT_URL,
  METABASE_URL,
  getAnalyticsStatus,
  getMcpStatus,
  runBacktest,
  runChat,
  runFactorPortfolio,
  runPortfolioOptimization,
  type ApiKeys,
  type AnalyticsStatus,
  type BacktestRequest,
  type BacktestResult,
  type FactorPortfolioRequest,
  type FactorPortfolioResult,
  type MCPStatus,
  type PortfolioOptimizationRequest,
  type PortfolioResult,
  type StrategyName,
} from "./api/client";
import ApiKeyPanel from "./components/ApiKeyPanel";
import BacktestForm, { buildBacktestPayload } from "./components/BacktestForm";
import ChatPanel from "./components/ChatPanel";
import FactorPortfolioPanel from "./components/FactorPortfolioPanel";
import PortfolioOptimizerPanel from "./components/PortfolioOptimizerPanel";
import AppShell from "./components/layout/AppShell";
import CollapsiblePanel from "./components/layout/CollapsiblePanel";
import Sidebar from "./components/layout/Sidebar";
import AnalyticsStatusPanel from "./components/panels/AnalyticsStatusPanel";
import McpStatusPanel from "./components/panels/McpStatusPanel";
import ParsedRequestPanel from "./components/panels/ParsedRequestPanel";
import TokenUsagePanel from "./components/panels/TokenUsagePanel";
import ResultDashboard from "./components/ResultDashboard";
import FactorPortfolioResultDashboard from "./components/portfolio/FactorPortfolioResultDashboard";
import PortfolioResultDashboard from "./components/portfolio/PortfolioResultDashboard";

const emptyApiKeys: ApiKeys = {
  chatUrl: DEFAULT_CHAT_URL,
  chatApiKey: "",
  model: DEFAULT_CHAT_MODEL,
  finnhubApiKey: "",
};
const defaultParameters: Record<StrategyName, string> = {
  sma_crossover: JSON.stringify({ fast_window: 20, slow_window: 50 }, null, 2),
  rsi_mean_reversion: JSON.stringify({ rsi_window: 14, lower: 30, upper: 70 }, null, 2),
  bollinger_reversion: JSON.stringify({ window: 20, std_dev: 2 }, null, 2),
  macd_crossover: JSON.stringify({ fast_period: 12, slow_period: 26, signal_period: 9 }, null, 2),
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
  const [portfolioResult, setPortfolioResult] = useState<PortfolioResult | null>(null);
  const [factorPortfolioResult, setFactorPortfolioResult] = useState<FactorPortfolioResult | null>(null);
  const [activeWorkflow, setActiveWorkflow] = useState<"backtest" | "portfolio" | "factor">("backtest");
  const [error, setError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [assistantMessage, setAssistantMessage] = useState<string | null>(null);
  const [parsedRequest, setParsedRequest] = useState<
    BacktestRequest | PortfolioOptimizationRequest | FactorPortfolioRequest | Record<string, unknown> | null
  >(null);
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown> | null>(null);
  const [usedChat, setUsedChat] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKeys>(emptyApiKeys);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [mcpStatusError, setMcpStatusError] = useState<string | null>(null);
  const [isMcpStatusLoading, setIsMcpStatusLoading] = useState(false);
  const [analyticsStatus, setAnalyticsStatus] = useState<AnalyticsStatus | null>(null);
  const [analyticsStatusError, setAnalyticsStatusError] = useState<string | null>(null);
  const [isAnalyticsStatusLoading, setIsAnalyticsStatusLoading] = useState(false);

  const parseError = useMemo(() => {
    try {
      JSON.parse(parametersText || "{}");
      return null;
    } catch (error) {
      return error instanceof Error ? error.message : "Parameters must be valid JSON.";
    }
  }, [parametersText]);

  const configSummary = useMemo(() => {
    const missing = [!apiKeys.chatApiKey.trim() ? "Chat key" : "", !apiKeys.finnhubApiKey.trim() ? "Finnhub" : ""].filter(Boolean);
    return missing.length ? `Missing ${missing.join(", ")}` : `${apiKeys.model.trim() || DEFAULT_CHAT_MODEL}`;
  }, [apiKeys.chatApiKey, apiKeys.finnhubApiKey, apiKeys.model]);

  const mcpSummary = useMemo(() => {
    if (isMcpStatusLoading) return "Checking";
    if (mcpStatusError) return "Error";
    if (!mcpStatus) return "Unknown";
    if (!mcpStatus.enabled) return "Disabled";
    return mcpStatus.connected ? "Connected" : "Offline";
  }, [isMcpStatusLoading, mcpStatus, mcpStatusError]);

  const analyticsSummary = useMemo(() => {
    if (isAnalyticsStatusLoading) return "Checking";
    if (analyticsStatusError) return "Error";
    if (!analyticsStatus) return "Unknown";
    if (!analyticsStatus.enabled) return "Disabled";
    return analyticsStatus.connected ? "Connected" : "Offline";
  }, [analyticsStatus, analyticsStatusError, isAnalyticsStatusLoading]);

  const shouldOpenConfig = !apiKeys.chatApiKey.trim() || !apiKeys.finnhubApiKey.trim();

  function handleStrategyChange(nextStrategy: StrategyName) {
    setStrategy(nextStrategy);
    setParametersText(defaultParameters[nextStrategy]);
  }

  const refreshMcpStatus = useCallback(async () => {
    setIsMcpStatusLoading(true);
    setMcpStatusError(null);
    try {
      const response = await getMcpStatus();
      setMcpStatus(response);
    } catch (error) {
      setMcpStatusError(error instanceof Error ? error.message : "MCP status check failed.");
    } finally {
      setIsMcpStatusLoading(false);
    }
  }, []);

  const refreshAnalyticsStatus = useCallback(async () => {
    setIsAnalyticsStatusLoading(true);
    setAnalyticsStatusError(null);
    try {
      const response = await getAnalyticsStatus();
      setAnalyticsStatus(response);
    } catch (error) {
      setAnalyticsStatusError(error instanceof Error ? error.message : "Analytics status check failed.");
    } finally {
      setIsAnalyticsStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMcpStatus();
    void refreshAnalyticsStatus();
  }, [refreshAnalyticsStatus, refreshMcpStatus]);

  async function handleSubmit() {
    setActiveWorkflow("backtest");
    if (parseError) {
      setError("Fix the parameters JSON before running the backtest.");
      return;
    }

    if (!apiKeys.finnhubApiKey.trim()) {
      setError("Finnhub API key is required for market data.");
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
      const response = await runBacktest(payload, apiKeys);
      setResult(response);
      setPortfolioResult(null);
      setFactorPortfolioResult(null);
      setParsedRequest(payload);
      setDiagnostics(response.diagnostics || null);
      setUsedChat(false);
      setAssistantMessage(null);
      void refreshMcpStatus();
      void refreshAnalyticsStatus();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Backtest failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleChatSubmit(message: string) {
    if (!apiKeys.chatApiKey.trim()) {
      setChatError("Chat API key is required for natural language parsing.");
      setError("Chat API key is required for natural language parsing.");
      return;
    }

    if (!apiKeys.finnhubApiKey.trim()) {
      setChatError("Finnhub API key is required for market data.");
      setError("Finnhub API key is required for market data.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setChatError(null);

    try {
      const response = await runChat(message, apiKeys);
      setAssistantMessage(response.assistant_message || null);
      setParsedRequest(response.parsed_request || null);
      setDiagnostics(response.diagnostics || response.backtest_result?.diagnostics || null);
      setUsedChat(true);

      if (response.status === "needs_input") {
        setChatError(null);
        setError(null);
        return;
      }

      if (response.result_type === "portfolio_optimization" && response.portfolio_result) {
        setPortfolioResult(response.portfolio_result);
        setFactorPortfolioResult(null);
        setActiveWorkflow("portfolio");
      } else if (response.result_type === "factor_portfolio" && response.factor_portfolio_result) {
        setFactorPortfolioResult(response.factor_portfolio_result);
        setPortfolioResult(null);
        setResult(null);
        setActiveWorkflow("factor");
      } else if (response.backtest_result) {
        setResult(response.backtest_result);
        setPortfolioResult(null);
        setFactorPortfolioResult(null);
        setActiveWorkflow("backtest");
      }
      void refreshMcpStatus();
      void refreshAnalyticsStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Chat request failed.";
      setChatError(message);
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handlePortfolioSubmit(payload: PortfolioOptimizationRequest) {
    setActiveWorkflow("portfolio");
    setIsLoading(true);
    setError(null);
    setChatError(null);

    if (!apiKeys.finnhubApiKey.trim()) {
      setIsLoading(false);
      setError("Finnhub API key is required for market data.");
      return;
    }

    try {
      const response = await runPortfolioOptimization(payload, apiKeys);
      setPortfolioResult(response.portfolio_result || null);
      setFactorPortfolioResult(null);
      setParsedRequest(response.parsed_request || payload);
      setDiagnostics(response.diagnostics || null);
      setUsedChat(false);
      setAssistantMessage(response.assistant_message || null);
      void refreshMcpStatus();
      void refreshAnalyticsStatus();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Portfolio optimization failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleFactorPortfolioSubmit(payload: FactorPortfolioRequest) {
    setActiveWorkflow("factor");
    setIsLoading(true);
    setError(null);
    setChatError(null);

    if (!apiKeys.finnhubApiKey.trim()) {
      setIsLoading(false);
      setError("Finnhub API key is required for market and factor data.");
      return;
    }

    try {
      const response = await runFactorPortfolio(payload, apiKeys);
      setFactorPortfolioResult(response.factor_portfolio_result || null);
      setPortfolioResult(null);
      setResult(null);
      setParsedRequest(response.parsed_request || payload);
      setDiagnostics(response.diagnostics || null);
      setUsedChat(false);
      setAssistantMessage(response.assistant_message || null);
      void refreshMcpStatus();
      void refreshAnalyticsStatus();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Factor portfolio construction failed.");
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

          <CollapsiblePanel title="LLM / API Configuration" defaultOpen={shouldOpenConfig} summary={configSummary}>
            <ApiKeyPanel apiKeys={apiKeys} onChange={setApiKeys} />
          </CollapsiblePanel>

          <CollapsiblePanel title="Manual Backtest" defaultOpen={false} summary={`${symbol.toUpperCase()} / ${lookback}`}>
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
          </CollapsiblePanel>

          <CollapsiblePanel title="Portfolio Optimizer" defaultOpen={false} summary="All stocks and sectors">
            <PortfolioOptimizerPanel isLoading={isLoading} onSubmit={handlePortfolioSubmit} />
          </CollapsiblePanel>

          <CollapsiblePanel title="Factor Portfolio" defaultOpen={false} summary="Quality, value, momentum">
            <FactorPortfolioPanel isLoading={isLoading} onSubmit={handleFactorPortfolioSubmit} />
          </CollapsiblePanel>

          <CollapsiblePanel title="MCP Diagnostics" defaultOpen={false} summary={mcpSummary}>
            <McpStatusPanel
              status={mcpStatus}
              isLoading={isMcpStatusLoading}
              error={mcpStatusError}
              diagnostics={diagnostics || result?.diagnostics || null}
              result={result}
              onRefresh={refreshMcpStatus}
            />
          </CollapsiblePanel>

          <CollapsiblePanel title="Analytics" defaultOpen={false} summary={analyticsSummary}>
            <AnalyticsStatusPanel
              status={analyticsStatus}
              isLoading={isAnalyticsStatusLoading}
              error={analyticsStatusError}
              metabaseUrl={METABASE_URL}
              onRefresh={refreshAnalyticsStatus}
            />
          </CollapsiblePanel>

          <CollapsiblePanel title="Parsed Request" defaultOpen={false} summary={parsedRequest ? "Latest intent" : "Empty"}>
            <ParsedRequestPanel parsedRequest={parsedRequest} result={result} variant="plain" />
          </CollapsiblePanel>

          <CollapsiblePanel title="Token / Cache" defaultOpen={false} summary={usedChat ? "Chat run" : "No chat run"}>
            <TokenUsagePanel diagnostics={diagnostics || result?.diagnostics} usedChat={usedChat} variant="plain" />
          </CollapsiblePanel>
        </Sidebar>
      }
    >
      {activeWorkflow === "factor" ? (
        <FactorPortfolioResultDashboard
          result={factorPortfolioResult}
          isLoading={isLoading}
          error={error}
        />
      ) : activeWorkflow === "portfolio" ? (
        <PortfolioResultDashboard
          result={portfolioResult}
          isLoading={isLoading}
          error={error}
          parsedRequest={parsedRequest}
        />
      ) : (
        <ResultDashboard
          result={result}
          isLoading={isLoading}
          error={error}
          parsedRequest={parsedRequest}
          diagnostics={diagnostics}
          usedChat={usedChat}
        />
      )}
    </AppShell>
  );
}
