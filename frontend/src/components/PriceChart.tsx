import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint, SignalPoint } from "../api/client";
import { axisColor, chartGrid, compactCurrency, tooltipStyle } from "./chartUtils";

type PriceChartProps = {
  price?: PricePoint[];
  signals?: SignalPoint[];
};

export default function PriceChart({ price = [], signals = [] }: PriceChartProps) {
  const buyMarkers = signals
    .filter((signal) => signal.type === "entry")
    .map((signal) => ({ date: signal.date, close: signal.price }));
  const sellMarkers = signals
    .filter((signal) => signal.type === "exit")
    .map((signal) => ({ date: signal.date, close: signal.price }));

  return (
    <section className="panel-shell p-4">
      <ChartHeader title="Price" subtitle={`${price.length} candles / ${signals.length} signals`} />
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={price} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={chartGrid} strokeDasharray="3 3" />
            <XAxis dataKey="date" stroke={axisColor} tick={{ fontSize: 11 }} minTickGap={32} />
            <YAxis stroke={axisColor} tick={{ fontSize: 11 }} tickFormatter={compactCurrency} domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: "#e8eef7" }}
              formatter={(value) => [compactCurrency(value), "Close"]}
            />
            <Line type="monotone" dataKey="close" stroke="#38d2d2" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Scatter name="Buy" data={buyMarkers} fill="#2dd47f" shape="triangle" isAnimationActive={false} />
            <Scatter name="Sell" data={sellMarkers} fill="#ff5c7a" shape="diamond" isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function ChartHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-3 flex items-center justify-between border-b border-line pb-3">
      <h2 className="section-title">{title}</h2>
      <span className="text-xs text-muted">{subtitle}</span>
    </div>
  );
}
