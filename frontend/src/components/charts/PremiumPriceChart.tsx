import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import type { BacktestResult } from "../../api/client";
import {
  deriveIndicatorSeries,
  toCandlestickSeries,
  toSignalMarkers,
  toVolumeSeries,
  type CandlePoint,
} from "../../lib/chartTransforms";
import { quantTheme } from "../../lib/chartThemes";
import { formatCompactNumber, formatCurrency } from "../../lib/numberFormatters";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type PremiumPriceChartProps = {
  result: BacktestResult;
};

function PremiumPriceChart({ result }: PremiumPriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [hovered, setHovered] = useState<CandlePoint | null>(null);
  const price = result.charts?.price || [];
  const signals = result.charts?.signals || [];
  const candles = useMemo(() => toCandlestickSeries(price), [price]);
  const volumes = useMemo(() => toVolumeSeries(price), [price]);
  const markers = useMemo(() => toSignalMarkers(signals), [signals]);
  const indicators = useMemo(() => deriveIndicatorSeries(price, result.request), [price, result.request]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !candles.length) return;

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: quantTheme.panel },
        textColor: quantTheme.axis,
        fontSize: 11,
      },
      grid: {
        vertLines: { color: quantTheme.gridline },
        horzLines: { color: quantTheme.gridline },
      },
      rightPriceScale: { borderColor: quantTheme.gridline },
      timeScale: { borderColor: quantTheme.gridline, timeVisible: false },
      crosshair: {
        vertLine: { color: "#5b6b82", width: 1, style: 3 },
        horzLine: { color: "#5b6b82", width: 1, style: 3 },
      },
    });

    chartRef.current = chart;
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#1fba78",
      downColor: "#e24d63",
      borderUpColor: "#1fba78",
      borderDownColor: "#e24d63",
      wickUpColor: "#74e5b1",
      wickDownColor: "#ff8796",
    });
    candleSeries.setData(candles);
    createSeriesMarkers(candleSeries, markers as never);

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
      color: quantTheme.volume,
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volumeSeries.setData(volumes);

    addLine(chart, indicators.sma_fast, quantTheme.strategy, "SMA Fast");
    addLine(chart, indicators.sma_slow, quantTheme.benchmark, "SMA Slow");
    addLine(chart, indicators.bollinger_upper, "#7784ff", "Bollinger Upper");
    addLine(chart, indicators.bollinger_middle, quantTheme.strategy, "Bollinger Middle");
    addLine(chart, indicators.bollinger_lower, "#7784ff", "Bollinger Lower");

    const candleByTime = new Map(candles.map((candle) => [candle.time, candle]));
    chart.subscribeCrosshairMove((param) => {
      const key = typeof param.time === "string" ? param.time : String(param.time || "");
      setHovered(candleByTime.get(key) || null);
    });
    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, volumes, markers, indicators]);

  if (!candles.length) {
    return (
      <SectionCard title="Price Terminal" subtitle="Candles, volume, signals, overlays">
        <EmptyState title="No price data" message="Run a backtest to populate the institutional price terminal." />
      </SectionCard>
    );
  }

  return (
    <SectionCard
      title="Price Terminal"
      subtitle={`${candles.length} daily candles / ${signals.length} strategy signals`}
      bodyClassName="relative p-0"
      action={
        hovered ? (
          <div className="hidden gap-3 text-[11px] text-muted md:flex">
            <span>{hovered.time}</span>
            <span>O {formatCurrency(hovered.open, 2)}</span>
            <span>H {formatCurrency(hovered.high, 2)}</span>
            <span>L {formatCurrency(hovered.low, 2)}</span>
            <span>C {formatCurrency(hovered.close, 2)}</span>
          </div>
        ) : null
      }
    >
      <div ref={containerRef} className="h-[460px] w-full" />
      <div className="absolute bottom-2 left-3 border border-line bg-ink/90 px-2 py-1 text-[11px] text-muted">
        Volume {formatCompactNumber(volumes[volumes.length - 1]?.value)}
      </div>
    </SectionCard>
  );
}

function addLine(
  chart: IChartApi,
  data: Array<{ time: string; value: number }> | undefined,
  color: string,
  title: string,
): ISeriesApi<"Line"> | null {
  if (!data?.length) return null;
  const series = chart.addSeries(LineSeries, {
    color,
    lineWidth: 1,
    title,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  series.setData(data);
  return series;
}

export default memo(PremiumPriceChart);
