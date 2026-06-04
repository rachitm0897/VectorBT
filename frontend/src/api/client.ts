export const DEFAULT_CHAT_URL = normalizeDefault("VITE_DEFAULT_CHAT_URL", "https://api.openai.com/v1");
export const DEFAULT_CHAT_MODEL = normalizeDefault("VITE_DEFAULT_MODEL", "gpt-4o-mini");
export const METABASE_URL = normalizeUrl(import.meta.env.VITE_METABASE_URL, "http://localhost:3000");

export type StrategyName = "sma_crossover" | "rsi_mean_reversion" | "bollinger_reversion";

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

export type PortfolioOptimizationRequest = {
  symbols: string[];
  sector?: string;
  lookback: "1mo" | "6mo" | "1y" | "2y" | "5y";
  resolution: "D";
  objective: "max_sharpe" | "min_volatility";
  risk_free_rate: number;
  allow_short: boolean;
  max_weight: number;
  num_frontier_portfolios: number;
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
  };
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
  diagnostics?: Record<string, unknown>;
  warnings?: string[];
  errors?: string[];
  missing_fields?: string[];
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
