export type StrategyName = "sma_crossover" | "rsi_mean_reversion" | "bollinger_reversion";

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
  backtest_result?: BacktestResult;
  diagnostics?: Record<string, unknown>;
  warnings?: string[];
  errors?: string[];
  missing_fields?: string[];
  details?: string;
};

export type AnalyticsStatus = {
  enabled: boolean;
  connected: boolean;
  metabase_url: string;
};

export type MCPStatus = {
  enabled: boolean;
  transport: string;
  server_command: string;
  server_args: string;
  connected: boolean;
  tools: string[];
  error: string | null;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function runBacktest(payload: BacktestRequest): Promise<BacktestResult> {
  const response = await fetch(`${API_BASE_URL}/api/backtest/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
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

export async function runChat(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
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

export async function fetchAnalyticsStatus(): Promise<AnalyticsStatus> {
  const response = await fetch(`${API_BASE_URL}/api/analytics/status/`);
  if (!response.ok) {
    throw new Error("Analytics status request failed.");
  }

  const data = (await response.json()) as Partial<AnalyticsStatus>;
  return {
    enabled: Boolean(data.enabled),
    connected: Boolean(data.connected),
    metabase_url: data.metabase_url || "http://localhost:3000",
  };
}

export async function fetchMCPStatus(): Promise<MCPStatus> {
  const response = await fetch(`${API_BASE_URL}/api/mcp/status/`);
  if (!response.ok) {
    throw new Error("MCP status request failed.");
  }

  const data = (await response.json()) as Partial<MCPStatus>;
  return {
    enabled: Boolean(data.enabled),
    transport: data.transport || "stdio",
    server_command: data.server_command || "python",
    server_args: data.server_args || "standalone_mcp_server/server.py",
    connected: Boolean(data.connected),
    tools: Array.isArray(data.tools) ? data.tools : [],
    error: data.error || null,
  };
}
