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
  sharpe_ratio?: number;
  max_drawdown_pct?: number;
  win_rate_pct?: number;
  total_trades?: number;
  final_value?: number;
};

export type PricePoint = {
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
};

export type SignalPoint = {
  date: string;
  type: "entry" | "exit" | string;
  price?: number;
};

export type EquityPoint = {
  date: string;
  value?: number;
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
    equity_curve?: EquityPoint[];
    drawdown_curve?: EquityPoint[];
    monte_carlo?: MonteCarloChart;
  };
  tables?: {
    trades?: Array<Record<string, unknown>>;
  };
  summary?: Record<string, number>;
  warnings?: string[];
  errors?: string[];
};

export type ChatResponse = {
  status: "success" | "error" | "needs_input";
  assistant_message?: string;
  parsed_request?: BacktestRequest | Record<string, unknown>;
  backtest_result?: BacktestResult;
  warnings?: string[];
  errors?: string[];
  missing_fields?: string[];
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
