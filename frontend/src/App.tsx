import { useCallback, useEffect, useMemo, useState } from "react";
import {
  DEFAULT_CHAT_MODEL,
  DEFAULT_CHAT_URL,
  METABASE_URL,
  fetchStrategyRegistry,
  getAnalyticsStatus,
  getMcpStatus,
  runChatStream,
  runFactorPortfolio,
  runMultiStockResearch,
  runPortfolioOptimization,
  runSingleStockResearch,
  type ApiKeys,
  type AnalyticsStatus,
  type BacktestRequest,
  type BacktestResult,
  type ChatStreamEvent,
  type FactorPortfolioRequest,
  type FactorPortfolioResult,
  type MCPStatus,
  type MultiStockResearchRequest,
  type PortfolioOptimizationRequest,
  type PortfolioResult,
  type ResearchResultEnvelope,
  type SingleStockResearchRequest,
  type StrategyRegistryItem,
} from "./api/client";
import A2UITemplateRenderer from "./components/A2UITemplateRenderer";
import ApiKeyPanel from "./components/ApiKeyPanel";
import ChatPanel from "./components/ChatPanel";
import FactorPortfolioPanel from "./components/FactorPortfolioPanel";
import ManualResearchLab from "./components/ManualResearchLab";
import PortfolioOptimizerPanel from "./components/PortfolioOptimizerPanel";
import StrategyDiscoveryLab from "./components/StrategyDiscoveryLab";
import AppShell from "./components/layout/AppShell";
import CollapsiblePanel from "./components/layout/CollapsiblePanel";
import EmptyState from "./components/layout/EmptyState";
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

type ActiveWorkflow = "research" | "backtest" | "portfolio" | "factor" | "empty";

export default function App() {
  const [strategies, setStrategies] = useState<StrategyRegistryItem[]>([]);
  const [strategyError, setStrategyError] = useState<string | null>(null);
  const [isStrategyLoading, setIsStrategyLoading] = useState(false);
  const [researchEnvelope, setResearchEnvelope] = useState<ResearchResultEnvelope | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [portfolioResult, setPortfolioResult] = useState<PortfolioResult | null>(null);
  const [factorPortfolioResult, setFactorPortfolioResult] = useState<FactorPortfolioResult | null>(null);
  const [activeWorkflow, setActiveWorkflow] = useState<ActiveWorkflow>("empty");
  const [error, setError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [assistantMessage, setAssistantMessage] = useState<string | null>(null);
  const [streamEvents, setStreamEvents] = useState<ChatStreamEvent[]>([]);
  const [parsedRequest, setParsedRequest] = useState<
    | BacktestRequest
    | PortfolioOptimizationRequest
    | FactorPortfolioRequest
    | SingleStockResearchRequest
    | MultiStockResearchRequest
    | Record<string, unknown>
    | null
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

  const refreshStrategies = useCallback(async () => {
    setIsStrategyLoading(true);
    setStrategyError(null);
    try {
      const response = await fetchStrategyRegistry({ limit: 200 });
      setStrategies(response.strategies || []);
    } catch (error) {
      setStrategyError(error instanceof Error ? error.message : "Strategy registry failed to load.");
    } finally {
      setIsStrategyLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStrategies();
    void refreshMcpStatus();
    void refreshAnalyticsStatus();
  }, [refreshAnalyticsStatus, refreshMcpStatus, refreshStrategies]);

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
    setStreamEvents([]);

    try {
      const response = await runChatStream(message, apiKeys, (event) => {
        setStreamEvents((current) => [...current.slice(-40), event]);
        if (event.event === "message.delta" && typeof event.data.content === "string") {
          setAssistantMessage(event.data.content);
        }
      });
      setAssistantMessage(response.assistant_message || null);
      setParsedRequest(response.parsed_request || null);
      setDiagnostics(response.diagnostics || response.backtest_result?.diagnostics || null);
      setUsedChat(true);
      setResearchEnvelope(null);

      if (response.status === "needs_input") {
        setChatError(null);
        setError(null);
        return;
      }
      if (response.result_type === "portfolio_optimization" && response.portfolio_result) {
        setPortfolioResult(response.portfolio_result);
        setFactorPortfolioResult(null);
        setResult(null);
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

  async function handleSingleResearch(payload: SingleStockResearchRequest) {
    if (!apiKeys.finnhubApiKey.trim()) {
      setError("Finnhub API key is required for market data.");
      return;
    }
    setActiveWorkflow("research");
    setIsLoading(true);
    setError(null);
    setChatError(null);
    try {
      const response = await runSingleStockResearch(payload, apiKeys);
      setResearchEnvelope(response);
      setResult(null);
      setPortfolioResult(null);
      setFactorPortfolioResult(null);
      setParsedRequest(payload);
      setDiagnostics(response.diagnostics || null);
      setUsedChat(false);
      setAssistantMessage(null);
      void refreshMcpStatus();
      void refreshAnalyticsStatus();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Single-stock research failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleMultiResearch(payload: MultiStockResearchRequest) {
    if (!apiKeys.finnhubApiKey.trim()) {
      setError("Finnhub API key is required for market data.");
      return;
    }
    setActiveWorkflow("research");
    setIsLoading(true);
    setError(null);
    setChatError(null);
    try {
      const response = await runMultiStockResearch(payload, apiKeys);
      setResearchEnvelope(response);
      setResult(null);
      setPortfolioResult(null);
      setFactorPortfolioResult(null);
      setParsedRequest(payload);
      setDiagnostics(response.diagnostics || null);
      setUsedChat(false);
      setAssistantMessage(null);
      void refreshMcpStatus();
      void refreshAnalyticsStatus();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Multi-stock research failed.");
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
      setResearchEnvelope(null);
      setFactorPortfolioResult(null);
      setResult(null);
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
      setResearchEnvelope(null);
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
            streamEvents={streamEvents}
            onSend={handleChatSubmit}
          />

          <ManualResearchLab
            strategies={strategies}
            isLoading={isLoading}
            onRunSingle={handleSingleResearch}
            onRunMulti={handleMultiResearch}
          />

          <StrategyDiscoveryLab isLoading={isLoading} />

          <CollapsiblePanel title="LLM / API Configuration" defaultOpen={shouldOpenConfig} summary={configSummary}>
            <ApiKeyPanel apiKeys={apiKeys} onChange={setApiKeys} />
          </CollapsiblePanel>

          <CollapsiblePanel title="Compatibility Optimizer" defaultOpen={false} summary="Raw Markowitz">
            <PortfolioOptimizerPanel isLoading={isLoading} onSubmit={handlePortfolioSubmit} />
          </CollapsiblePanel>

          <CollapsiblePanel title="Compatibility Factor Portfolio" defaultOpen={false} summary="Score tilt">
            <FactorPortfolioPanel isLoading={isLoading} onSubmit={handleFactorPortfolioSubmit} />
          </CollapsiblePanel>

          <CollapsiblePanel title="MCP Diagnostics" defaultOpen={false} summary={mcpSummary}>
            <McpStatusPanel
              status={mcpStatus}
              isLoading={isMcpStatusLoading}
              error={mcpStatusError}
              diagnostics={diagnostics || result?.diagnostics || researchEnvelope?.diagnostics || null}
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
      <div className="space-y-4">
        <RegistryStrip
          strategies={strategies}
          isLoading={isStrategyLoading}
          error={strategyError}
          onRefresh={refreshStrategies}
        />
        {activeWorkflow === "research" ? (
          <ResearchWorkspace envelope={researchEnvelope} isLoading={isLoading} error={error} />
        ) : activeWorkflow === "factor" ? (
          <FactorPortfolioResultDashboard result={factorPortfolioResult} isLoading={isLoading} error={error} />
        ) : activeWorkflow === "portfolio" ? (
          <PortfolioResultDashboard
            result={portfolioResult}
            isLoading={isLoading}
            error={error}
            parsedRequest={parsedRequest}
          />
        ) : activeWorkflow === "backtest" ? (
          <ResultDashboard
            result={result}
            isLoading={isLoading}
            error={error}
            parsedRequest={parsedRequest}
            diagnostics={diagnostics}
            usedChat={usedChat}
          />
        ) : (
          <EmptyState
            title="No research run loaded"
            message="Use the AI chat, manual research lab, or discovery lab to start an MCP-backed workflow."
          />
        )}
      </div>
    </AppShell>
  );
}

function ResearchWorkspace({
  envelope,
  isLoading,
  error,
}: {
  envelope: ResearchResultEnvelope | null;
  isLoading: boolean;
  error: string | null;
}) {
  if (isLoading) {
    return <EmptyState title="Running MCP workflow" message="Fetching data, generating signals, optimizing, and building artifacts." />;
  }
  if (error && !envelope) {
    return <EmptyState title="Research failed" message={error} />;
  }
  if (!envelope) {
    return <EmptyState title="No MCP envelope" message="The workflow did not return a research envelope." />;
  }
  return (
    <div className="space-y-4">
      {error ? <div className="border border-red/60 bg-red/10 p-3 text-sm text-red">{error}</div> : null}
      <A2UITemplateRenderer envelope={envelope} />
    </div>
  );
}

function RegistryStrip({
  strategies,
  isLoading,
  error,
  onRefresh,
}: {
  strategies: StrategyRegistryItem[];
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const runnable = strategies.filter((strategy) => strategy.runnable).length;
  const singleAsset = strategies.filter((strategy) => strategy.execution_type === "single_asset_signal").length;
  return (
    <section className="panel-shell p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="section-title">Strategy Registry</h2>
          <div className="mt-2 flex flex-wrap gap-2 font-mono text-xs text-muted">
            <span className="border border-line bg-ink px-2 py-1">{strategies.length} total</span>
            <span className="border border-line bg-ink px-2 py-1">{runnable} runnable</span>
            <span className="border border-line bg-ink px-2 py-1">{singleAsset} signal engines</span>
          </div>
        </div>
        <button
          className="border border-line bg-ink px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted hover:border-green hover:text-green"
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
        >
          {isLoading ? "Loading" : "Refresh"}
        </button>
      </div>
      {error ? <div className="mt-3 border border-red/60 bg-red/10 p-3 text-xs text-red">{error}</div> : null}
      <div className="mt-3 max-h-40 overflow-auto border border-line">
        <table className="min-w-full border-collapse font-mono text-xs">
          <thead className="bg-panel2 text-muted">
            <tr>
              <th className="border-b border-line px-3 py-2 text-left">ID</th>
              <th className="border-b border-line px-3 py-2 text-left">Name</th>
              <th className="border-b border-line px-3 py-2 text-left">Readiness</th>
              <th className="border-b border-line px-3 py-2 text-left">Execution</th>
            </tr>
          </thead>
          <tbody>
            {strategies.slice(0, 40).map((strategy) => (
              <tr key={strategy.strategy_id} className="odd:bg-ink even:bg-panel">
                <td className="border-b border-line px-3 py-2 text-green">{strategy.strategy_id}</td>
                <td className="border-b border-line px-3 py-2 text-text">{strategy.name}</td>
                <td className="border-b border-line px-3 py-2 text-muted">{strategy.readiness}</td>
                <td className="border-b border-line px-3 py-2 text-muted">{strategy.execution_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
