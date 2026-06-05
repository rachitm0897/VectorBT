import type { EquityPoint, MonteCarloChart, PricePoint, SignalPoint } from "../api/client";
import { asNumber } from "./numberFormatters";

export type CandlePoint = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type VolumePoint = {
  time: string;
  value: number;
  color: string;
};

export type EquitySeriesPoint = {
  time: string;
  strategy: number | null;
  buy_hold: number | null;
  spy: number | null;
};

export type DrawdownPoint = {
  time: string;
  drawdown_pct: number;
};

export type MonteCarloBandPoint = {
  day: number;
  p5: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  p95: number | null;
  [sampleKey: `sample_${number}`]: number | null;
};

export type MonthlyReturnPoint = {
  year: number;
  month: number;
  monthLabel: string;
  return_pct: number;
};

export type RollingMetricPoint = {
  time: string;
  rolling_return_pct: number | null;
  rolling_volatility_pct: number | null;
  rolling_sharpe: number | null;
  rolling_win_rate_pct: number | null;
};

const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function toCandlestickSeries(priceData: PricePoint[] = []): CandlePoint[] {
  return priceData
    .map((point) => {
      const open = asNumber(point.open);
      const high = asNumber(point.high);
      const low = asNumber(point.low);
      const close = asNumber(point.close);
      const time = point.time || point.date;
      if (!time || open === null || high === null || low === null || close === null) return null;
      return { time, open, high, low, close };
    })
    .filter((point): point is CandlePoint => point !== null);
}

export function toVolumeSeries(priceData: PricePoint[] = []): VolumePoint[] {
  return priceData
    .map((point) => {
      const value = asNumber(point.volume) ?? 0;
      const open = asNumber(point.open);
      const close = asNumber(point.close);
      const time = point.time || point.date;
      if (!time) return null;
      return {
        time,
        value,
        color: close !== null && open !== null && close >= open ? "rgba(47, 212, 138, 0.24)" : "rgba(255, 93, 115, 0.24)",
      };
    })
    .filter((point): point is VolumePoint => point !== null);
}

export function toSignalMarkers(signals: SignalPoint[] = []) {
  return signals
    .map((signal) => {
      const type = String(signal.type || "").toLowerCase();
      const time = signal.time || signal.date;
      if (!time) return null;
      const isBuy = type === "buy" || type === "entry";
      const isSell = type === "sell" || type === "exit";
      if (!isBuy && !isSell) return null;
      return {
        time,
        position: isBuy ? "belowBar" : "aboveBar",
        color: isBuy ? "#35d98c" : "#ff637d",
        shape: isBuy ? "arrowUp" : "arrowDown",
        text: isBuy ? "B" : "S",
        size: 1,
      } as const;
    })
    .filter(Boolean);
}

export function toEquitySeries(equityCurve: EquityPoint[] = []): EquitySeriesPoint[] {
  return equityCurve
    .map((point) => {
      const time = point.time || point.date;
      if (!time) return null;
      return {
        time,
        strategy: asNumber(point.strategy) ?? asNumber(point.value),
        buy_hold: asNumber(point.buy_hold),
        spy: asNumber(point.spy),
      };
    })
    .filter((point): point is EquitySeriesPoint => point !== null);
}

export function normalizeBenchmarkSeries(equityCurve: EquityPoint[] = [], priceData: PricePoint[] = []): EquitySeriesPoint[] {
  const equity = toEquitySeries(equityCurve);
  if (!equity.length) return [];
  if (equity.some((point) => point.buy_hold !== null)) return equity;

  const priceByTime = new Map(
    priceData
      .map((point) => [point.time || point.date, asNumber(point.close)] as const)
      .filter((entry): entry is readonly [string, number] => Boolean(entry[0]) && entry[1] !== null),
  );
  const firstClose = priceByTime.get(equity[0].time);
  const firstStrategy = equity[0].strategy;
  if (!firstClose || !firstStrategy) return equity;

  return equity.map((point) => {
    const close = priceByTime.get(point.time);
    return {
      ...point,
      buy_hold: close ? firstStrategy * (close / firstClose) : null,
    };
  });
}

export function toDrawdownSeries(drawdownCurve: EquityPoint[] = [], equityCurve: EquityPoint[] = []): DrawdownPoint[] {
  const direct = drawdownCurve
    .map((point) => {
      const time = point.time || point.date;
      const drawdown = asNumber(point.drawdown_pct);
      if (!time || drawdown === null) return null;
      return { time, drawdown_pct: drawdown };
    })
    .filter((point): point is DrawdownPoint => point !== null);

  if (direct.length) return direct.map((point) => ({ ...point, drawdown_pct: point.drawdown_pct > 0 ? -point.drawdown_pct : point.drawdown_pct }));

  let peak = 0;
  return toEquitySeries(equityCurve)
    .map((point) => {
      const value = point.strategy;
      if (value === null) return null;
      peak = Math.max(peak, value);
      return { time: point.time, drawdown_pct: peak > 0 ? (value / peak - 1) * 100 : 0 };
    })
    .filter((point): point is DrawdownPoint => point !== null);
}

export function toMonteCarloBands(monteCarlo?: MonteCarloChart): MonteCarloBandPoint[] {
  const maxLength = Math.max(
    monteCarlo?.p5?.length || 0,
    monteCarlo?.p25?.length || 0,
    monteCarlo?.p50?.length || 0,
    monteCarlo?.p75?.length || 0,
    monteCarlo?.p95?.length || 0,
  );

  return Array.from({ length: maxLength }, (_, index) => {
    const point: MonteCarloBandPoint = {
      day: monteCarlo?.p50?.[index]?.day ?? index,
      p5: asNumber(monteCarlo?.p5?.[index]?.value),
      p25: asNumber(monteCarlo?.p25?.[index]?.value),
      p50: asNumber(monteCarlo?.p50?.[index]?.value),
      p75: asNumber(monteCarlo?.p75?.[index]?.value),
      p95: asNumber(monteCarlo?.p95?.[index]?.value),
    };

    monteCarlo?.sample_paths?.slice(0, 12).forEach((path, pathIndex) => {
      point[`sample_${pathIndex}`] = asNumber(path.values?.[index]?.value);
    });

    return point;
  });
}

export function deriveMonteCarloFinalReturns(monteCarlo?: MonteCarloChart): number[] {
  const returns =
    monteCarlo?.sample_paths
      ?.map((path) => {
        const values = path.values || [];
        const first = asNumber(values[0]?.value);
        const last = asNumber(values[values.length - 1]?.value);
        if (!first || last === null) return null;
        return (last / first - 1) * 100;
      })
      .filter((value): value is number => value !== null) || [];

  if (returns.length) return returns;

  return [monteCarlo?.p5, monteCarlo?.p25, monteCarlo?.p50, monteCarlo?.p75, monteCarlo?.p95]
    .map((path) => {
      const first = asNumber(path?.[0]?.value);
      const last = asNumber(path?.[path.length - 1]?.value);
      if (!first || last === null) return null;
      return (last / first - 1) * 100;
    })
    .filter((value): value is number => value !== null);
}

export function deriveMonthlyReturns(equityCurve: EquityPoint[] = []): MonthlyReturnPoint[] {
  const grouped = new Map<string, { first: number; last: number; year: number; month: number }>();
  for (const point of toEquitySeries(equityCurve)) {
    const value = point.strategy;
    if (value === null) continue;
    const date = new Date(point.time);
    if (Number.isNaN(date.getTime())) continue;
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth();
    const key = `${year}-${month}`;
    const current = grouped.get(key);
    if (!current) grouped.set(key, { first: value, last: value, year, month });
    else current.last = value;
  }

  return Array.from(grouped.values()).map((item) => ({
    year: item.year,
    month: item.month,
    monthLabel: monthLabels[item.month],
    return_pct: item.first ? (item.last / item.first - 1) * 100 : 0,
  }));
}

export function deriveRollingMetrics(equityCurve: EquityPoint[] = [], window = 30): RollingMetricPoint[] {
  const equity = toEquitySeries(equityCurve).filter((point) => point.strategy !== null);
  const returns = equity.map((point, index) => {
    if (index === 0) return 0;
    const previous = equity[index - 1].strategy;
    const current = point.strategy;
    return previous && current ? current / previous - 1 : 0;
  });

  return equity.map((point, index) => {
    if (index < window) {
      return {
        time: point.time,
        rolling_return_pct: null,
        rolling_volatility_pct: null,
        rolling_sharpe: null,
        rolling_win_rate_pct: null,
      };
    }

    const slice = returns.slice(index - window + 1, index + 1);
    const totalReturn = slice.reduce((acc, value) => acc * (1 + value), 1) - 1;
    const average = slice.reduce((sum, value) => sum + value, 0) / slice.length;
    const variance = slice.reduce((sum, value) => sum + (value - average) ** 2, 0) / slice.length;
    const volatility = Math.sqrt(variance);
    const winRate = slice.filter((value) => value > 0).length / slice.length;
    return {
      time: point.time,
      rolling_return_pct: totalReturn * 100,
      rolling_volatility_pct: volatility * Math.sqrt(252) * 100,
      rolling_sharpe: volatility > 0 ? (average / volatility) * Math.sqrt(252) : null,
      rolling_win_rate_pct: winRate * 100,
    };
  });
}

export function deriveBuyHoldReturn(priceData: PricePoint[] = []): number | null {
  const closes = priceData.map((point) => asNumber(point.close)).filter((value): value is number => value !== null);
  if (closes.length < 2 || closes[0] === 0) return null;
  return (closes[closes.length - 1] / closes[0] - 1) * 100;
}

export function deriveIndicatorSeries(priceData: PricePoint[] = [], request?: { strategy?: string; parameters?: Record<string, unknown> }) {
  const candles = toCandlestickSeries(priceData);
  const strategy = request?.strategy;
  const parameters = request?.parameters || {};
  const closeValues = candles.map((point) => point.close);

  if (strategy === "sma_crossover") {
    const fast = asNumber(parameters.fast_window) ?? 20;
    const slow = asNumber(parameters.slow_window) ?? 50;
    return {
      sma_fast: rollingAverage(candles, closeValues, fast),
      sma_slow: rollingAverage(candles, closeValues, slow),
    };
  }

  if (strategy === "bollinger_reversion") {
    const window = asNumber(parameters.window) ?? 20;
    const stdDev = asNumber(parameters.std_dev) ?? 2;
    const middle = rollingAverage(candles, closeValues, window);
    return {
      bollinger_middle: middle,
      bollinger_upper: rollingBollinger(candles, closeValues, window, stdDev, 1),
      bollinger_lower: rollingBollinger(candles, closeValues, window, stdDev, -1),
    };
  }

  if (strategy === "macd_crossover") {
    const fastPeriod = asNumber(parameters.fast_period) ?? 12;
    const slowPeriod = asNumber(parameters.slow_period) ?? 26;
    const signalPeriod = asNumber(parameters.signal_period) ?? 9;
    const fast = exponentialMovingAverage(closeValues, fastPeriod);
    const slow = exponentialMovingAverage(closeValues, slowPeriod);
    const macdValues = fast.map((value, index) =>
      value === null || slow[index] === null ? null : value - (slow[index] as number),
    );
    const signalValues = exponentialMovingAverage(macdValues, signalPeriod);
    return {
      macd: toIndicatorPoints(candles, macdValues),
      signal: toIndicatorPoints(candles, signalValues),
      histogram: toIndicatorPoints(
        candles,
        macdValues.map((value, index) =>
          value === null || signalValues[index] === null
            ? null
            : value - (signalValues[index] as number),
        ),
      ),
    };
  }

  return {};
}

function exponentialMovingAverage(values: Array<number | null>, period: number): Array<number | null> {
  const result: Array<number | null> = Array(values.length).fill(null);
  let ema: number | null = null;
  let validCount = 0;
  const multiplier = 2 / (period + 1);

  values.forEach((value, index) => {
    if (value === null) return;
    validCount += 1;
    ema = ema === null ? value : (value - ema) * multiplier + ema;
    if (validCount >= period) result[index] = ema;
  });
  return result;
}

function toIndicatorPoints(candles: CandlePoint[], values: Array<number | null>) {
  return candles
    .map((point, index) => {
      const value = values[index];
      return value === null ? null : { time: point.time, value };
    })
    .filter((point): point is { time: string; value: number } => point !== null);
}

function rollingAverage(candles: CandlePoint[], values: number[], window: number) {
  return candles
    .map((point, index) => {
      if (index + 1 < window) return null;
      const slice = values.slice(index - window + 1, index + 1);
      return { time: point.time, value: slice.reduce((sum, value) => sum + value, 0) / slice.length };
    })
    .filter((point): point is { time: string; value: number } => point !== null);
}

function rollingBollinger(candles: CandlePoint[], values: number[], window: number, stdDev: number, direction: 1 | -1) {
  return candles
    .map((point, index) => {
      if (index + 1 < window) return null;
      const slice = values.slice(index - window + 1, index + 1);
      const mean = slice.reduce((sum, value) => sum + value, 0) / slice.length;
      const variance = slice.reduce((sum, value) => sum + (value - mean) ** 2, 0) / slice.length;
      return { time: point.time, value: mean + direction * stdDev * Math.sqrt(variance) };
    })
    .filter((point): point is { time: string; value: number } => point !== null);
}
