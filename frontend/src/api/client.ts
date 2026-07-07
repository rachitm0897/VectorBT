export const DEFAULT_CHAT_URL = normalizeDefault("VITE_DEFAULT_CHAT_URL", "https://api.openai.com/v1");
export const DEFAULT_CHAT_MODEL = normalizeDefault("VITE_DEFAULT_MODEL", "gpt-4o-mini");
export const METABASE_URL = normalizeUrl(import.meta.env.VITE_METABASE_URL, "http://localhost:3000");

export type StrategyName = string;

export type LlmConfig = {
  chatUrl: string;
  chatApiKey: string;
  model: string;
  finnhubApiKey: string;
};

export type ApiKeys = LlmConfig;

export type BacktestRequest = {
  symbol: string;
  strategy: StrategyName;
  parameters: Record<string, unknown>;
  lookback: string;
  resolution: "D";
  initial_cash: number;
  fees: number;
  monte_carlo: {
    enabled: boolean;
    days: number;
    simulations: number;
    method: "bootstrap";
  };
};

export type StrategyRegistryItem = {
  strategy_id: string;
  name: string;
  aliases?: string[];
  family?: string;
  description?: string;
  source_type?: string;
  horizon_bucket?: string | null;
  execution_type?: "single_asset_signal" | "cross_sectional_ranking" | "portfolio_strategy" | "research_only" | string;
  readiness?: "BACKTEST_READY" | "MISSING_DATA" | "RULES_INCOMPLETE" | "BACKTEST_FAILED" | "RESEARCH_ONLY" | "DEPRECATED" | string;
  runnable?: boolean;
  executable?: boolean;
  usability_status?: "executable" | "catalogue_only" | "missing_data" | "incomplete_rules" | "failed" | "deprecated" | string;
  status_label?: string;
  long_only?: boolean;
  long_short?: boolean;
  template_hint?: string;
  final_score?: number | null;
  active?: boolean;
  deprecated?: boolean;
};

export type StrategyDetails = StrategyRegistryItem & {
  source_type?: string;
  source_references?: Array<Record<string, unknown>>;
  required_data?: string[];
  required_features?: string[];
  parameter_schema?: Record<string, unknown>;
  default_parameters?: Record<string, unknown>;
  signal_rules?: Record<string, unknown>;
  ranking_rules?: Record<string, unknown>;
  implementation_version?: string;
  classification_metrics?: Record<string, unknown>;
  risk_score?: number | null;
  return_score?: number | null;
  risk_adjusted_score?: number | null;
  robustness_score?: number | null;
  active?: boolean;
  deprecated?: boolean;
  source_hash?: string | null;
};

export type StrategyRegistryResponse = {
  status: "success" | "error";
  count?: number;
  total_count?: number;
  summary?: StrategyRegistrySummary;
  strategies?: StrategyRegistryItem[];
  message?: string;
  errors?: string[];
};

export type StrategyRegistrySummary = {
  generated_at?: string;
  total_strategies?: number;
  executable_strategies?: number;
  catalogue_only_strategies?: number;
  imported_strategies?: number;
  built_in_strategies?: number;
  failed_imports?: number;
  missing_data_strategies?: number;
  incomplete_rule_strategies?: number;
  failed_strategies?: number;
  deprecated_strategies?: number;
  readiness_counts?: Record<string, number>;
  execution_type_counts?: Record<string, number>;
  import?: Record<string, unknown>;
};

export type StrategyDetailsResponse = {
  status: "success" | "error";
  strategy?: StrategyDetails;
  message?: string;
  errors?: string[];
};

export type UITemplateSpec = {
  template_id: string;
  title?: string | null;
  props?: Record<string, unknown>;
  artifacts?: Array<Record<string, unknown>>;
  warnings?: string[];
};

export type ResearchResultEnvelope = {
  status: "success" | "error" | string;
  workflow_type?: string;
  run_id?: string | null;
  strategy?: StrategyDetails | Record<string, unknown> | null;
  strategy_version?: string | null;
  universe?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
  data_quality?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  allocations?: Record<string, unknown>;
  trades?: Array<Record<string, unknown>>;
  equity?: Array<Record<string, unknown>>;
  drawdown?: Array<Record<string, unknown>>;
  monte_carlo?: Record<string, unknown> | null;
  frontier?: Array<Record<string, unknown>>;
  comparison?: Record<string, unknown>;
  warnings?: string[];
  errors?: string[];
  artifacts?: Array<Record<string, unknown>>;
  ui_hint?: string | null;
  ui_spec?: UITemplateSpec | Record<string, unknown> | null;
  persistence?: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
  message?: string;
};

export type StrategyCandidate = Record<string, unknown>;

export type StrategyDiscoveryResponse = {
  status: "success" | "error";
  candidates?: StrategyCandidate[];
  count?: number;
  message?: string;
  errors?: string[];
};

export type SingleStockResearchRequest = {
  symbol: string;
  strategy_id: string;
  parameters: Record<string, unknown>;
  lookback: "1mo" | "6mo" | "1y" | "2y" | "5y";
  resolution: "D";
  initial_cash: number;
  fees: number;
  monte_carlo?: {
    enabled?: boolean;
    days?: number;
    simulations?: number;
    seed?: number | null;
    method?: "bootstrap" | "block_bootstrap";
    block_size?: number;
    thresholds?: number[];
    mode?: "strategy_returns";
  };
};

export type MultiStockResearchRequest = {
  symbols: string[];
  strategy_id: string;
  parameters: Record<string, unknown>;
  lookback: "1mo" | "6mo" | "1y" | "2y" | "5y";
  resolution: "D";
  initial_cash: number;
  fees: number;
  optimization?: Record<string, unknown>;
  monte_carlo?: {
    enabled?: boolean;
    days?: number;
    simulations?: number;
    seed?: number | null;
    method?: "bootstrap" | "block_bootstrap";
    block_size?: number;
    thresholds?: number[];
    mode?: "portfolio_returns";
  };
};

export type StockUniverseItem = {
  ticker: string;
  name?: string;
  sector?: string;
  exchange?: string;
  currency?: string;
  market_cap?: string;
  risk_level?: string;
  iv_profile?: string;
  strategy_fit?: string;
  notes?: string;
};

export type PortfolioScenarioName = "neutral" | "bullish" | "bearish" | "crash";

export type PortfolioScenarioAssumptions = {
  drift_shift_annual?: number;
  volatility_multiplier?: number;
  initial_shock_pct?: number;
};

export type PortfolioScenarioOverride = Partial<PortfolioScenarioAssumptions>;

export type PortfolioMonteCarloConfig = {
  enabled: boolean;
  days: number;
  simulations: number;
  block_size: number;
  seed: number | null;
  scenarios: PortfolioScenarioName[];
  scenario_overrides: Partial<Record<PortfolioScenarioName, PortfolioScenarioOverride>>;
};

export type PortfolioOptimizationRequest = {
  symbols: string[];
  sector?: string;
  lookback: "1mo" | "6mo" | "1y" | "2y" | "5y";
  resolution: "D";
  initial_cash?: number;
  fees?: number;
  objective: "max_sharpe" | "min_volatility" | "target_return" | "target_volatility";
  risk_free_rate: number;
  target_return?: number | null;
  target_volatility?: number | null;
  allow_short: boolean;
  min_weight?: number | null;
  max_weight: number;
  gross_exposure_limit?: number;
  net_exposure?: number;
  covariance_regularization?: number;
  covariance_method?: string;
  num_frontier_portfolios: number;
  monte_carlo?: PortfolioMonteCarloConfig;
};

export type RawAssetMonteCarloRequest = {
  symbol: string;
  lookback: "1mo" | "6mo" | "1y" | "2y" | "5y";
  resolution: "D";
  start_value: number;
  days: number;
  simulations: number;
  method: "bootstrap" | "block_bootstrap";
  seed?: number | null;
};

export type FactorModelConfiguration = {
  enabled: boolean;
  normalization_mode: "universe" | "sector";
  weights: {
    fundamental_quality: number;
    valuation: number;
    momentum: number;
    analyst: number;
    financial_risk: number;
  };
  minimum_data_coverage_pct: number;
  selection_method: "top_n" | "top_percentile" | "minimum_score" | "all_eligible";
  top_n: number;
  top_percentile: number;
  minimum_score: number | null;
};

export type FactorPortfolioOptimizationConfig = {
  objective: "max_sharpe" | "min_volatility";
  minimum_weight: number;
  maximum_weight: number;
  risk_free_rate: number;
  expected_return_method: "historical" | "factor_tilted";
  num_frontier_portfolios?: number;
};

export type ScoreTiltConfig = {
  enabled: boolean;
  strength: number;
  maximum_adjustment_pct: number;
};

export type FactorPortfolioRequest = {
  symbols: string[];
  sector?: string;
  selection_mode: "symbols" | "sector";
  lookback: "1mo" | "6mo" | "1y" | "2y" | "5y";
  resolution: "D";
  factor_model: FactorModelConfiguration;
  optimization: FactorPortfolioOptimizationConfig;
  score_tilt: ScoreTiltConfig;
  monte_carlo: PortfolioMonteCarloConfig;
};

export type PortfolioMetrics = {
  expected_annual_return_pct?: number;
  annual_volatility_pct?: number;
  sharpe_ratio?: number;
};

export type PortfolioChartPoint = {
  portfolio_volatility?: number;
  portfolio_return?: number;
  annual_volatility_pct?: number;
  expected_annual_return_pct?: number;
  sharpe_ratio?: number;
};

export type RandomPortfolioPoint = PortfolioChartPoint & {
  weights?: Record<string, number>;
};

export type OptimalPortfolioPoint = PortfolioChartPoint & {
  weights?: Record<string, number>;
};

export type IndividualAssetPoint = PortfolioChartPoint & {
  ticker?: string;
};

export type EfficientFrontierPoint = PortfolioChartPoint & {
  annual_volatility_pct?: number;
  expected_annual_return_pct?: number;
};

export type CorrelationRow = {
  symbol: string;
  [symbol: string]: string | number | undefined;
};

export type PortfolioScenarioSummary = {
  expected_return_pct?: number;
  probability_positive_return_pct?: number;
  probability_loss_above_10_pct?: number;
  p5_return_pct?: number;
  p25_return_pct?: number;
  p50_return_pct?: number;
  p75_return_pct?: number;
  p95_return_pct?: number;
  expected_final_value?: number;
  p5_final_value?: number;
  p50_final_value?: number;
  p95_final_value?: number;
  average_max_drawdown_pct?: number;
  worst_simulated_drawdown_pct?: number;
};

export type PortfolioScenarioCompact = {
  name: PortfolioScenarioName | string;
  label?: string;
  assumptions?: PortfolioScenarioAssumptions;
  summary?: PortfolioScenarioSummary;
};

export type PortfolioScenarioAnalysis = {
  enabled?: boolean;
  config?: {
    enabled?: boolean;
    days?: number;
    simulations?: number;
    block_size?: number;
    seed?: number | null;
    portfolio_start_value?: number;
  };
  scenarios?: PortfolioScenarioCompact[];
};

export type PortfolioScenarioChart = {
  assumptions?: PortfolioScenarioAssumptions;
  summary?: PortfolioScenarioSummary;
  percentile_paths?: Partial<Record<"p5" | "p25" | "p50" | "p75" | "p95", number[]>>;
  sample_paths?: number[][];
};

export type PortfolioResult = {
  status: "success" | "error";
  objective?: string;
  symbols?: string[];
  selection_mode?: "symbols" | "sector" | string;
  sector?: string | null;
  symbols_used?: string[];
  rejected_symbols?: string[];
  weights?: Record<string, number>;
  metrics?: PortfolioMetrics;
  data_quality?: Record<string, unknown>;
  artifact_id?: string;
  artifact_url?: string;
  charts?: {
    random_portfolios?: RandomPortfolioPoint[];
    efficient_frontier?: EfficientFrontierPoint[];
    min_volatility_portfolio?: OptimalPortfolioPoint;
    max_sharpe_portfolio?: OptimalPortfolioPoint;
    individual_assets?: IndividualAssetPoint[];
    correlation_matrix?: CorrelationRow[];
    scenario_analysis?: Record<string, PortfolioScenarioChart>;
  };
  scenario_analysis?: PortfolioScenarioAnalysis;
  warnings?: string[];
};

export type PortfolioOptimizationResponse = {
  status: "success" | "error";
  message?: string;
  assistant_message?: string;
  parsed_request?: PortfolioOptimizationRequest | Record<string, unknown>;
  result_type?: "portfolio_optimization" | string;
  portfolio_result?: PortfolioResult;
  diagnostics?: Record<string, unknown>;
  warnings?: string[];
  errors?: string[];
};

export type FactorScoreRow = {
  ticker?: string;
  company_name?: string;
  sector?: string;
  raw_factor_values?: Record<string, unknown>;
  normalized_factor_scores?: Record<string, number | null>;
  fundamental_quality_score?: number | null;
  valuation_score?: number | null;
  momentum_score?: number | null;
  analyst_score?: number | null;
  financial_risk_score?: number | null;
  quantitative_alpha_score?: number | null;
  combined_portfolio_score?: number | null;
  data_coverage_pct?: number | null;
  requested_factor_weights?: Record<string, number>;
  effective_factor_weights?: Record<string, number>;
  selection_status?: string;
  selection_reason?: string;
  expected_return_original?: number | null;
  expected_return_adjusted?: number | null;
  final_portfolio_weight?: number | null;
};

export type FactorPortfolioResult = {
  status?: "success" | "error";
  tool?: "construct_factor_portfolio" | string;
  run_id?: string;
  request_summary?: Record<string, unknown>;
  universe_summary?: {
    symbols_requested?: number;
    symbols_scored?: number;
    symbols_selected?: number;
  };
  factor_model_configuration?: Partial<FactorModelConfiguration> & Record<string, unknown>;
  factor_scores?: FactorScoreRow[];
  selected_stocks?: FactorScoreRow[];
  rejected_stocks?: Array<{ ticker?: string; reason?: string }>;
  optimization_result?: {
    objective?: string;
    weights?: Record<string, number>;
    metrics?: PortfolioMetrics;
    artifact_id?: string;
    artifact_url?: string;
  };
  portfolio_weights?: Record<string, number>;
  scenario_analysis?: PortfolioScenarioAnalysis | null;
  scenario_charts?: Record<string, PortfolioScenarioChart>;
  data_sources?: Record<string, unknown>;
  calculation_timestamp?: string;
  artifact_id?: string;
  artifact_url?: string;
  warnings?: string[];
};

export type FactorPortfolioResponse = {
  status: "success" | "error";
  message?: string;
  assistant_message?: string;
  parsed_request?: FactorPortfolioRequest | Record<string, unknown>;
  result_type?: "factor_portfolio" | string;
  factor_portfolio_result?: FactorPortfolioResult;
  diagnostics?: Record<string, unknown>;
  warnings?: string[];
  errors?: string[];
};

export type MetricSet = {
  total_return_pct?: number;
  buy_hold_return_pct?: number;
  alpha_vs_buy_hold_pct?: number;
  sharpe_ratio?: number;
  max_drawdown_pct?: number;
  win_rate_pct?: number;
  total_trades?: number;
  final_value?: number;
};

export type PricePoint = {
  time?: string;
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
};

export type SignalPoint = {
  time?: string;
  date: string;
  type: "entry" | "exit" | string;
  price?: number;
};

export type EquityPoint = {
  time?: string;
  date: string;
  value?: number;
  strategy?: number;
  buy_hold?: number;
  spy?: number;
  drawdown_pct?: number;
};

export type MonteCarloPoint = {
  day: number;
  value?: number;
};

export type MonteCarloChart = {
  p5?: MonteCarloPoint[];
  p25?: MonteCarloPoint[];
  p50?: MonteCarloPoint[];
  p75?: MonteCarloPoint[];
  p95?: MonteCarloPoint[];
  sample_paths?: Array<{ path?: number; values?: MonteCarloPoint[] }>;
};

export type BacktestResult = {
  status: "success" | "error";
  message?: string;
  request?: {
    symbol?: string;
    strategy?: string;
    parameters?: Record<string, unknown>;
  };
  metrics?: MetricSet;
  charts?: {
    price?: PricePoint[];
    signals?: SignalPoint[];
    indicators?: Record<string, Array<Record<string, unknown>>>;
    equity_curve?: EquityPoint[];
    drawdown_curve?: EquityPoint[];
    monte_carlo?: MonteCarloChart;
    monthly_returns?: Array<Record<string, unknown>>;
    rolling_metrics?: Array<Record<string, unknown>>;
    parameter_sweep?: Array<Record<string, unknown>>;
  };
  tables?: {
    trades?: Array<Record<string, unknown>>;
  };
  summary?: Record<string, number>;
  diagnostics?: Record<string, unknown>;
  warnings?: string[];
  errors?: string[];
};

export type ChatResponse = {
  status: "success" | "error" | "needs_input";
  assistant_message?: string;
  parsed_request?: BacktestRequest | Record<string, unknown>;
  result_type?: "strategy_backtest" | "portfolio_optimization" | string;
  backtest_result?: BacktestResult;
  portfolio_result?: PortfolioResult;
  factor_portfolio_result?: FactorPortfolioResult;
  diagnostics?: Record<string, unknown>;
  warnings?: string[];
  errors?: string[];
  missing_fields?: string[];
};

export type ChatStreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

export type MCPStatus = {
  enabled: boolean;
  transport: string;
  server_url?: string;
  connected: boolean;
  tools: string[];
  approved_tools?: string[];
  error: string | null;
};

export type AnalyticsStatus = {
  enabled: boolean;
  connected: boolean;
  database: string;
  host: string;
  metabase_url: string;
  error: string | null;
};

export type SystemHealth = {
  status: "success" | "error";
  backend?: Record<string, unknown>;
  mcp?: MCPStatus;
  analytics?: AnalyticsStatus;
  metabase?: Record<string, unknown>;
  registry?: StrategyRegistrySummary | Record<string, unknown>;
  message?: string;
  errors?: string[];
};

export type McpToolInventory = {
  status: "success" | "error";
  mcp?: MCPStatus;
  public_tools?: Array<{ name: string; status: string }>;
  legacy_tools?: Array<{ name: string; status: string }>;
  message?: string;
};

export type SystemDiagnostics = {
  status: "success" | "error";
  recent_mcp_calls?: Array<Record<string, unknown>>;
  recent_errors?: Array<Record<string, unknown>>;
  cache?: Record<string, unknown>;
  artifacts?: Record<string, unknown>;
  database?: AnalyticsStatus | Record<string, unknown>;
};

export type ResearchRunSummary = {
  run_id?: string;
  workflow_type?: string;
  status?: string;
  strategy_id?: string | null;
  symbols?: string[];
  created_at?: string | null;
  updated_at?: string | null;
};

const DEFAULT_API_BASE_URL = import.meta.env.PROD ? "https://qfsplatform.com/insta_backtester" : "http://localhost:8000/api";

function normalizeApiBaseUrl(value: string | undefined): string {
  const base = (value || DEFAULT_API_BASE_URL).trim().replace(/\/+$/g, "");

  if (!base) {
    return DEFAULT_API_BASE_URL;
  }

  if (base.endsWith("/api") || base.endsWith("/v1") || base.endsWith("/vectorbt_api/v1") || base.endsWith("/insta_backtester_api/v1")) {
    return base;
  }

  if (base.endsWith("/vectorbt_api") || base.endsWith("/insta_backtester_api")) {
    return `${base}/v1`;
  }

  return `${base}/api`;
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
const MCP_STATUS_PATH = import.meta.env.VITE_MCP_STATUS_PATH || "/mcp/status/";

function normalizeDefault(envName: "VITE_DEFAULT_CHAT_URL" | "VITE_DEFAULT_MODEL", fallback: string): string {
  const rawValue = envName === "VITE_DEFAULT_CHAT_URL" ? import.meta.env.VITE_DEFAULT_CHAT_URL : import.meta.env.VITE_DEFAULT_MODEL;
  const value = String(rawValue || fallback).trim();
  return value || fallback;
}

function normalizeUrl(value: string | undefined, fallback: string): string {
  const normalized = String(value || fallback).trim().replace(/\/+$/g, "");
  return normalized || fallback;
}

function buildApiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function buildBackendPathUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (normalizedPath.startsWith("/api/")) {
    return `${API_BASE_URL.replace(/\/api$/g, "")}${normalizedPath}`;
  }
  return buildApiUrl(normalizedPath);
}

function normalizeLlmConfig(apiKeys?: Partial<ApiKeys>): ApiKeys {
  const chatUrl = apiKeys?.chatUrl?.trim() || DEFAULT_CHAT_URL;
  const model = apiKeys?.model?.trim() || DEFAULT_CHAT_MODEL;
  return {
    chatUrl,
    model,
    chatApiKey: apiKeys?.chatApiKey?.trim() || "",
    finnhubApiKey: apiKeys?.finnhubApiKey?.trim() || "",
  };
}

function buildConfigPayload(apiKeys?: Partial<ApiKeys>, includeChatConfig = true): Record<string, string> {
  const config = normalizeLlmConfig(apiKeys);
  const payload: Record<string, string> = {
    finnhub_api_key: config.finnhubApiKey,
  };

  if (includeChatConfig) {
    payload.chat_url = config.chatUrl;
    payload.chat_api_key = config.chatApiKey;
    payload.model = config.model;
  }

  return payload;
}

function buildRequestHeaders(apiKeys?: ApiKeys, includeChatConfig = true): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const config = normalizeLlmConfig(apiKeys);

  if (includeChatConfig) {
    headers["X-Chat-URL"] = config.chatUrl;
    headers["X-OpenAI-Base-URL"] = config.chatUrl;
    headers["X-Chat-Model"] = config.model;
    headers["X-OpenAI-Model"] = config.model;
    if (config.chatApiKey) {
      headers["X-Chat-API-Key"] = config.chatApiKey;
      headers["X-OpenAI-API-Key"] = config.chatApiKey;
    }
  }

  if (config.finnhubApiKey) {
    headers["X-Finnhub-API-Key"] = config.finnhubApiKey;
  }

  return headers;
}

function buildFinnhubRequestHeaders(apiKeys?: ApiKeys): HeadersInit {
  return buildRequestHeaders(apiKeys, false);
}

export async function runBacktest(payload: BacktestRequest, apiKeys?: ApiKeys): Promise<BacktestResult> {
  const response = await fetch(buildApiUrl("/backtest/"), {
    method: "POST",
    headers: buildFinnhubRequestHeaders(apiKeys),
    body: JSON.stringify({ ...payload, ...buildConfigPayload(apiKeys, false) }),
  });

  let data: BacktestResult | null = null;
  try {
    data = (await response.json()) as BacktestResult;
  } catch {
    data = null;
  }

  if (!response.ok || data?.status === "error") {
    const details = data?.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data?.message || "Backtest request failed."}${details}`);
  }

  if (!data) {
    throw new Error("Backend returned an empty response.");
  }

  return data;
}

export async function fetchStrategyRegistry(options: {
  query?: string;
  family?: string;
  readiness?: string;
  execution_type?: string;
  executable_only?: boolean;
  limit?: number;
} = {}): Promise<StrategyRegistryResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(options)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(buildApiUrl(`/strategies/${suffix}`), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  const data = (await response.json()) as StrategyRegistryResponse;
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Strategy registry request failed."}${details}`);
  }
  return data;
}

export async function fetchStrategyRegistryStatus(): Promise<{ status: "success" | "error"; summary?: StrategyRegistrySummary; total_count?: number }> {
  const response = await fetch(buildApiUrl("/strategies/status/"), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const data = (await response.json()) as { status: "success" | "error"; summary?: StrategyRegistrySummary; total_count?: number; message?: string; errors?: string[] };
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Strategy registry status request failed."}${details}`);
  }
  return data;
}

export async function syncStrategyRegistry(): Promise<Record<string, unknown>> {
  const response = await fetch(buildApiUrl("/strategies/sync/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = (await response.json()) as Record<string, unknown>;
  if (!response.ok || data.status === "error") {
    const errors = Array.isArray(data.errors) ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${String(data.message || "Strategy registry sync failed.")}${errors}`);
  }
  return data;
}

export async function fetchStrategyDetails(strategyId: string): Promise<StrategyDetailsResponse> {
  const response = await fetch(buildApiUrl(`/strategies/${encodeURIComponent(strategyId)}/`), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  const data = (await response.json()) as StrategyDetailsResponse;
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Strategy details request failed."}${details}`);
  }
  return data;
}

export async function runSingleStockResearch(
  payload: SingleStockResearchRequest,
  apiKeys?: ApiKeys,
): Promise<ResearchResultEnvelope> {
  const response = await fetch(buildApiUrl("/research/single/"), {
    method: "POST",
    headers: buildFinnhubRequestHeaders(apiKeys),
    body: JSON.stringify({ ...payload, ...buildConfigPayload(apiKeys, false) }),
  });

  let data: ResearchResultEnvelope | null = null;
  try {
    data = (await response.json()) as ResearchResultEnvelope;
  } catch {
    data = null;
  }

  if (!data) {
    throw new Error("Backend returned an empty single-stock research response.");
  }
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Single-stock research failed."}${details}`);
  }
  return data;
}

export async function runMultiStockResearch(
  payload: MultiStockResearchRequest,
  apiKeys?: ApiKeys,
): Promise<ResearchResultEnvelope> {
  const response = await fetch(buildApiUrl("/research/multi/"), {
    method: "POST",
    headers: buildFinnhubRequestHeaders(apiKeys),
    body: JSON.stringify({ ...payload, ...buildConfigPayload(apiKeys, false) }),
  });

  let data: ResearchResultEnvelope | null = null;
  try {
    data = (await response.json()) as ResearchResultEnvelope;
  } catch {
    data = null;
  }

  if (!data) {
    throw new Error("Backend returned an empty multi-stock research response.");
  }
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Multi-stock research failed."}${details}`);
  }
  return data;
}

export async function discoverStrategyCandidates(payload: {
  query: string;
  sources: string[];
  max_results_per_source: number;
  max_candidates: number;
  start_year?: number | null;
  end_year?: number | null;
}): Promise<StrategyDiscoveryResponse> {
  const response = await fetch(buildApiUrl("/discovery/candidates/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await response.json()) as StrategyDiscoveryResponse;
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Strategy discovery failed."}${details}`);
  }
  return data;
}

export async function reviewStrategyCandidate(
  candidateId: string,
  payload: {
    action: "approve" | "reject" | "mark_duplicate" | "request_changes";
    reviewer?: string;
    reviewer_note?: string;
    edits?: Record<string, unknown>;
  },
): Promise<Record<string, unknown>> {
  const response = await fetch(buildApiUrl(`/discovery/candidates/${encodeURIComponent(candidateId)}/review/`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await response.json()) as Record<string, unknown>;
  if (!response.ok || data.status === "error") {
    const errors = Array.isArray(data.errors) ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${String(data.message || "Candidate review failed.")}${errors}`);
  }
  return data;
}

export async function processApprovedStrategy(candidateId: string): Promise<Record<string, unknown>> {
  const response = await fetch(buildApiUrl(`/discovery/candidates/${encodeURIComponent(candidateId)}/process/`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit: 1 }),
  });
  const data = (await response.json()) as Record<string, unknown>;
  if (!response.ok || data.status === "error") {
    const errors = Array.isArray(data.errors) ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${String(data.message || "Approved strategy processing failed.")}${errors}`);
  }
  return data;
}

export async function fetchSectors(): Promise<string[]> {
  const response = await fetch(buildApiUrl("/universe/sectors/"), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  const data = (await response.json()) as { status?: string; sectors?: string[]; errors?: string[]; message?: string };
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Universe sectors request failed."}${details}`);
  }
  return Array.isArray(data.sectors) ? data.sectors : [];
}

export async function fetchStocksBySector(sector?: string): Promise<StockUniverseItem[]> {
  const params = sector ? `?sector=${encodeURIComponent(sector)}` : "";
  const response = await fetch(buildApiUrl(`/universe/stocks/${params}`), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  const data = (await response.json()) as {
    status?: string;
    stocks?: StockUniverseItem[];
    errors?: string[];
    message?: string;
  };
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Universe stocks request failed."}${details}`);
  }
  return Array.isArray(data.stocks) ? data.stocks : [];
}

export async function resolveSymbolsForSector(sector: string): Promise<{ sector: string; symbols: string[]; count: number }> {
  const response = await fetch(buildApiUrl(`/universe/resolve-sector/?sector=${encodeURIComponent(sector)}`), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const data = (await response.json()) as {
    status?: string;
    sector?: string;
    symbols?: string[];
    count?: number;
    errors?: string[];
    message?: string;
  };
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Sector symbol resolution failed."}${details}`);
  }
  return {
    sector: data.sector || sector,
    symbols: Array.isArray(data.symbols) ? data.symbols : [],
    count: Number(data.count || data.symbols?.length || 0),
  };
}

export async function runRawMarkowitzResearch(
  payload: PortfolioOptimizationRequest,
  apiKeys?: ApiKeys,
): Promise<ResearchResultEnvelope> {
  const response = await fetch(buildApiUrl("/research/portfolio/raw/"), {
    method: "POST",
    headers: buildFinnhubRequestHeaders(apiKeys),
    body: JSON.stringify({ ...payload, ...buildConfigPayload(apiKeys, false) }),
  });
  let data: ResearchResultEnvelope | null = null;
  try {
    data = (await response.json()) as ResearchResultEnvelope;
  } catch {
    data = null;
  }
  if (!data) {
    throw new Error("Backend returned an empty raw Markowitz response.");
  }
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Raw Markowitz optimization failed."}${details}`);
  }
  return data;
}

export async function runRawAssetMonteCarlo(
  payload: RawAssetMonteCarloRequest,
  apiKeys?: ApiKeys,
): Promise<ResearchResultEnvelope> {
  const response = await fetch(buildApiUrl("/research/monte-carlo/raw/"), {
    method: "POST",
    headers: buildFinnhubRequestHeaders(apiKeys),
    body: JSON.stringify({ ...payload, ...buildConfigPayload(apiKeys, false) }),
  });
  let data: ResearchResultEnvelope | null = null;
  try {
    data = (await response.json()) as ResearchResultEnvelope;
  } catch {
    data = null;
  }
  if (!data) {
    throw new Error("Backend returned an empty raw Monte Carlo response.");
  }
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Raw Monte Carlo failed."}${details}`);
  }
  return data;
}

export async function runPortfolioOptimization(
  payload: PortfolioOptimizationRequest,
  apiKeys?: ApiKeys,
): Promise<PortfolioOptimizationResponse> {
  const response = await fetch(buildApiUrl("/portfolio/optimize/"), {
    method: "POST",
    headers: buildFinnhubRequestHeaders(apiKeys),
    body: JSON.stringify({ ...payload, ...buildConfigPayload(apiKeys, false) }),
  });

  let data: PortfolioOptimizationResponse | null = null;
  try {
    data = (await response.json()) as PortfolioOptimizationResponse;
  } catch {
    data = null;
  }

  if (!data) {
    throw new Error("Backend returned an empty portfolio optimization response.");
  }

  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.assistant_message || data.message || "Portfolio optimization failed."}${details}`);
  }

  return data;
}

export async function runFactorPortfolio(
  payload: FactorPortfolioRequest,
  apiKeys?: ApiKeys,
): Promise<FactorPortfolioResponse> {
  const response = await fetch(buildApiUrl("/portfolio/factor/"), {
    method: "POST",
    headers: buildFinnhubRequestHeaders(apiKeys),
    body: JSON.stringify({ ...payload, ...buildConfigPayload(apiKeys, false) }),
  });

  let data: FactorPortfolioResponse | null = null;
  try {
    data = (await response.json()) as FactorPortfolioResponse;
  } catch {
    data = null;
  }

  if (!data) {
    throw new Error("Backend returned an empty factor portfolio response.");
  }

  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.assistant_message || data.message || "Factor portfolio construction failed."}${details}`);
  }

  return data;
}

export async function runChat(message: string, apiKeys?: ApiKeys): Promise<ChatResponse> {
  const response = await fetch(buildApiUrl("/chat/"), {
    method: "POST",
    headers: buildRequestHeaders(apiKeys),
    body: JSON.stringify({ message, ...buildConfigPayload(apiKeys, true) }),
  });

  let data: ChatResponse | null = null;
  try {
    data = (await response.json()) as ChatResponse;
  } catch {
    data = null;
  }

  if (!data) {
    throw new Error("Backend returned an empty chat response.");
  }

  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.assistant_message || "Chat request failed."}${details}`);
  }

  return data;
}

export async function runChatStream(
  message: string,
  apiKeys: ApiKeys | undefined,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<ChatResponse> {
  const response = await fetch(buildApiUrl("/chat/stream/"), {
    method: "POST",
    headers: buildRequestHeaders(apiKeys),
    body: JSON.stringify({ message, ...buildConfigPayload(apiKeys, true) }),
  });

  if (!response.body) {
    return runChat(message, apiKeys);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: ChatResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\n\n/);
    buffer = events.pop() || "";
    for (const rawEvent of events) {
      const parsed = parseSseEvent(rawEvent);
      if (!parsed) continue;
      onEvent(parsed);
      if (parsed.event === "message.completed") {
        completed = parsed.data as ChatResponse;
      }
      if (parsed.event === "error") {
        const message = String(parsed.data.message || "Chat stream failed.");
        const errors = Array.isArray(parsed.data.errors) ? ` (${parsed.data.errors.join(", ")})` : "";
        throw new Error(`${message}${errors}`);
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer);
    if (parsed) {
      onEvent(parsed);
      if (parsed.event === "message.completed") {
        completed = parsed.data as ChatResponse;
      }
    }
  }

  if (!response.ok && !completed) {
    throw new Error("Chat stream failed.");
  }
  return completed || runChat(message, apiKeys);
}

export async function getMcpStatus(): Promise<MCPStatus> {
  const response = await fetch(buildBackendPathUrl(MCP_STATUS_PATH), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  const data = (await response.json()) as MCPStatus;
  if (!response.ok) {
    throw new Error(data?.error || "MCP status request failed.");
  }
  return data;
}

function parseSseEvent(rawEvent: string): ChatStreamEvent | null {
  const lines = rawEvent.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (!eventLine || dataLines.length === 0) {
    return null;
  }

  const event = eventLine.replace(/^event:\s*/, "").trim();
  const dataText = dataLines.map((line) => line.replace(/^data:\s*/, "")).join("\n");
  try {
    const data = JSON.parse(dataText) as Record<string, unknown>;
    return { event, data };
  } catch {
    return { event, data: { content: dataText } };
  }
}

export async function getAnalyticsStatus(): Promise<AnalyticsStatus> {
  const response = await fetch(buildApiUrl("/analytics/status/"), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  const data = (await response.json()) as AnalyticsStatus;
  if (!response.ok) {
    throw new Error(data?.error || "Analytics status request failed.");
  }
  return data;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const response = await fetch(buildApiUrl("/system/health/"), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const data = (await response.json()) as SystemHealth;
  if (!response.ok || data.status === "error") {
    throw new Error(data.message || "System health request failed.");
  }
  return data;
}

export async function getMcpToolInventory(): Promise<McpToolInventory> {
  const response = await fetch(buildApiUrl("/mcp/tools/"), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const data = (await response.json()) as McpToolInventory;
  if (!response.ok || data.status === "error") {
    throw new Error(data.message || "MCP tool inventory request failed.");
  }
  return data;
}

export async function getSystemDiagnostics(): Promise<SystemDiagnostics> {
  const response = await fetch(buildApiUrl("/system/diagnostics/"), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const data = (await response.json()) as SystemDiagnostics;
  if (!response.ok || data.status === "error") {
    throw new Error("System diagnostics request failed.");
  }
  return data;
}

export async function listResearchRuns(limit = 25): Promise<{ status: "success" | "error"; runs: ResearchRunSummary[] }> {
  const response = await fetch(buildApiUrl(`/research/runs/?limit=${encodeURIComponent(String(limit))}`), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const data = (await response.json()) as { status: "success" | "error"; runs?: ResearchRunSummary[]; message?: string; errors?: string[] };
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Research run listing failed."}${details}`);
  }
  return { status: "success", runs: data.runs || [] };
}

export async function getResearchRun(runId: string): Promise<{ status: "success" | "error"; run?: ResearchResultEnvelope }> {
  const response = await fetch(buildApiUrl(`/research/runs/${encodeURIComponent(runId)}/`), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const data = (await response.json()) as { status: "success" | "error"; run?: ResearchResultEnvelope; message?: string; errors?: string[] };
  if (!response.ok || data.status === "error") {
    const details = data.errors?.length ? ` (${data.errors.join(", ")})` : "";
    throw new Error(`${data.message || "Research run lookup failed."}${details}`);
  }
  return data;
}
