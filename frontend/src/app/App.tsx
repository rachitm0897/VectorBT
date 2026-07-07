import { useCallback, useEffect, useMemo, useState } from "react";
import {
  DEFAULT_CHAT_MODEL,
  DEFAULT_CHAT_URL,
  fetchStrategyRegistry,
  getAnalyticsStatus,
  getMcpStatus,
  runMultiStockResearch,
  runRawAssetMonteCarlo,
  runRawMarkowitzResearch,
  runSingleStockResearch,
  syncStrategyRegistry,
  type AnalyticsStatus,
  type ApiKeys,
  type MCPStatus,
  type MultiStockResearchRequest,
  type PortfolioOptimizationRequest,
  type RawAssetMonteCarloRequest,
  type ResearchResultEnvelope,
  type SingleStockResearchRequest,
  type StrategyRegistryItem,
  type StrategyRegistrySummary,
} from "../api/client";
import AIResearchChat from "../features/chat/AIResearchChat";
import StrategyDiscoveryLab from "../features/discovery/StrategyDiscoveryLab";
import ManualResearchLab from "../features/manual-lab/ManualResearchLab";
import SystemSettings from "../features/system/SystemSettings";
import TerminalShell from "./layout/TerminalShell";
import type { PrimaryTab } from "./tabs";

const apiKeyStorageKey = "vectorbt.mcp.apiKeys";

const emptyApiKeys: ApiKeys = {
  chatUrl: DEFAULT_CHAT_URL,
  chatApiKey: "",
  model: DEFAULT_CHAT_MODEL,
  finnhubApiKey: "",
};

export default function App() {
  const [activeTab, setActiveTab] = useState<PrimaryTab>("chat");
  const [apiKeys, setApiKeysState] = useState<ApiKeys>(() => loadApiKeys());
  const [strategies, setStrategies] = useState<StrategyRegistryItem[]>([]);
  const [registrySummary, setRegistrySummary] = useState<StrategyRegistrySummary | null>(null);
  const [strategyError, setStrategyError] = useState<string | null>(null);
  const [isStrategyLoading, setIsStrategyLoading] = useState(false);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [analyticsStatus, setAnalyticsStatus] = useState<AnalyticsStatus | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState("");
  const [manualEnvelope, setManualEnvelope] = useState<ResearchResultEnvelope | null>(null);
  const [chatEnvelope, setChatEnvelope] = useState<ResearchResultEnvelope | null>(null);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [isWorkflowLoading, setIsWorkflowLoading] = useState(false);

  const visibleRegistrySummary = useMemo(() => registrySummary || deriveSummary(strategies), [registrySummary, strategies]);

  const setApiKeys = useCallback((next: ApiKeys) => {
    setApiKeysState(next);
    localStorage.setItem(apiKeyStorageKey, JSON.stringify(next));
  }, []);

  const refreshStrategies = useCallback(async () => {
    setIsStrategyLoading(true);
    setStrategyError(null);
    try {
      const response = await fetchStrategyRegistry({ limit: 1000 });
      setStrategies(response.strategies || []);
      setRegistrySummary(response.summary || deriveSummary(response.strategies || []));
    } catch (error) {
      setStrategyError(error instanceof Error ? error.message : "Strategy registry failed to load.");
    } finally {
      setIsStrategyLoading(false);
    }
  }, []);

  const refreshMcpStatus = useCallback(async () => {
    try {
      setMcpStatus(await getMcpStatus());
    } catch {
      setMcpStatus(null);
    }
  }, []);

  const refreshAnalyticsStatus = useCallback(async () => {
    try {
      setAnalyticsStatus(await getAnalyticsStatus());
    } catch {
      setAnalyticsStatus(null);
    }
  }, []);

  const handleSyncRegistry = useCallback(async () => {
    setStrategyError(null);
    setIsStrategyLoading(true);
    try {
      const response = await syncStrategyRegistry();
      const summary = objectValue(response.summary);
      if (summary) setRegistrySummary(summary as StrategyRegistrySummary);
      await refreshStrategies();
    } catch (error) {
      setStrategyError(error instanceof Error ? error.message : "Strategy registry sync failed.");
    } finally {
      setIsStrategyLoading(false);
    }
  }, [refreshStrategies]);

  useEffect(() => {
    void refreshStrategies();
    void refreshMcpStatus();
    void refreshAnalyticsStatus();
  }, [refreshAnalyticsStatus, refreshMcpStatus, refreshStrategies]);

  async function runWorkflow<T>(operation: () => Promise<T>, onSuccess: (result: T) => void, fallback: string) {
    setIsWorkflowLoading(true);
    setWorkflowError(null);
    try {
      const result = await operation();
      onSuccess(result);
      void refreshMcpStatus();
      void refreshAnalyticsStatus();
    } catch (error) {
      setWorkflowError(error instanceof Error ? error.message : fallback);
    } finally {
      setIsWorkflowLoading(false);
    }
  }

  function requireFinnhub(): boolean {
    if (!apiKeys.finnhubApiKey.trim()) {
      setWorkflowError("Finnhub API key is required for market data workflows.");
      setActiveTab("system");
      return false;
    }
    return true;
  }

  return (
    <TerminalShell
      activeTab={activeTab}
      onTabChange={setActiveTab}
      mcpStatus={mcpStatus}
      analyticsStatus={analyticsStatus}
      registrySummary={visibleRegistrySummary}
    >
      {workflowError ? (
        <div className="mb-4 border border-red/60 bg-red/10 p-3 text-sm text-red">
          {workflowError}
          <button className="ml-3 border border-red/50 px-2 py-1 text-xs" type="button" onClick={() => setWorkflowError(null)}>
            Clear
          </button>
        </div>
      ) : null}

      {activeTab === "chat" ? (
        <AIResearchChat apiKeys={apiKeys} onResult={setChatEnvelope} />
      ) : null}

      {activeTab === "manual" ? (
        <ManualResearchLab
          strategies={strategies}
          selectedStrategyId={selectedStrategyId}
          isLoading={isWorkflowLoading}
          lastEnvelope={manualEnvelope || chatEnvelope}
          onRunSingle={async (payload: SingleStockResearchRequest) => {
            if (!requireFinnhub()) return;
            await runWorkflow(
              () => runSingleStockResearch(payload, apiKeys),
              setManualEnvelope,
              "Single-stock research failed.",
            );
          }}
          onRunMulti={async (payload: MultiStockResearchRequest) => {
            if (!requireFinnhub()) return;
            await runWorkflow(
              () => runMultiStockResearch(payload, apiKeys),
              setManualEnvelope,
              "Multi-stock research failed.",
            );
          }}
          onRunRawMarkowitz={async (payload: PortfolioOptimizationRequest) => {
            if (!requireFinnhub()) return;
            await runWorkflow(
              () => runRawMarkowitzResearch(payload, apiKeys),
              setManualEnvelope,
              "Raw Markowitz optimization failed.",
            );
          }}
          onRunRawMonteCarlo={async (payload: RawAssetMonteCarloRequest) => {
            if (!requireFinnhub()) return;
            await runWorkflow(
              () => runRawAssetMonteCarlo(payload, apiKeys),
              setManualEnvelope,
              "Raw asset Monte Carlo failed.",
            );
          }}
        />
      ) : null}

      {activeTab === "discovery" ? (
        <StrategyDiscoveryLab
          strategies={strategies}
          summary={visibleRegistrySummary}
          isRegistryLoading={isStrategyLoading}
          registryError={strategyError}
          onRefreshRegistry={refreshStrategies}
          onSyncRegistry={() => void handleSyncRegistry()}
          onUseStrategy={(strategyId) => {
            setSelectedStrategyId(strategyId);
            setActiveTab("manual");
          }}
        />
      ) : null}

      {activeTab === "system" ? (
        <SystemSettings
          apiKeys={apiKeys}
          onApiKeysChange={setApiKeys}
          registrySummary={visibleRegistrySummary}
          onSyncRegistry={handleSyncRegistry}
          onRefreshRegistry={refreshStrategies}
          onRefreshMcp={refreshMcpStatus}
          onRefreshAnalytics={refreshAnalyticsStatus}
        />
      ) : null}
    </TerminalShell>
  );
}

function loadApiKeys(): ApiKeys {
  try {
    const parsed = JSON.parse(localStorage.getItem(apiKeyStorageKey) || "{}") as Partial<ApiKeys>;
    return {
      chatUrl: parsed.chatUrl || DEFAULT_CHAT_URL,
      chatApiKey: parsed.chatApiKey || "",
      model: parsed.model || DEFAULT_CHAT_MODEL,
      finnhubApiKey: parsed.finnhubApiKey || "",
    };
  } catch {
    return emptyApiKeys;
  }
}

function deriveSummary(strategies: StrategyRegistryItem[]): StrategyRegistrySummary {
  return {
    total_strategies: strategies.length,
    executable_strategies: strategies.filter((strategy) => strategy.executable || strategy.runnable).length,
    catalogue_only_strategies: strategies.filter((strategy) => strategy.usability_status === "catalogue_only").length,
    imported_strategies: strategies.filter((strategy) => strategy.source_type !== "built_in").length,
    built_in_strategies: strategies.filter((strategy) => strategy.source_type === "built_in").length,
    failed_imports: 0,
    missing_data_strategies: strategies.filter((strategy) => strategy.usability_status === "missing_data").length,
    incomplete_rule_strategies: strategies.filter((strategy) => strategy.usability_status === "incomplete_rules").length,
    failed_strategies: strategies.filter((strategy) => strategy.usability_status === "failed").length,
    deprecated_strategies: strategies.filter((strategy) => strategy.usability_status === "deprecated").length,
  };
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}
