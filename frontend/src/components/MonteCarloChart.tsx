import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonteCarloChart as MonteCarloChartType } from "../api/client";
import { axisColor, chartGrid, compactCurrency, tooltipStyle } from "./chartUtils";

type MonteCarloChartProps = {
  data?: MonteCarloChartType;
  summary?: Record<string, number>;
};

type CombinedPoint = {
  day: number;
  p5?: number;
  p25?: number;
  p50?: number;
  p75?: number;
  p95?: number;
  [sampleKey: `sample_${number}`]: number | undefined;
};

export default function MonteCarloChart({ data, summary = {} }: MonteCarloChartProps) {
  const chartData = combineMonteCarlo(data);
  const sampleKeys = Object.keys(chartData[0] || {}).filter((key) => key.startsWith("sample_")).slice(0, 6);

  return (
    <section className="panel-shell p-4">
      <div className="mb-3 flex items-center justify-between border-b border-line pb-3">
        <h2 className="section-title">Monte Carlo</h2>
        <span className="text-xs text-muted">
          Expected {formatPct(summary.monte_carlo_expected_return_pct)} / Positive{" "}
          {formatPct(summary.probability_positive_return_pct)}
        </span>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={chartGrid} strokeDasharray="3 3" />
            <XAxis dataKey="day" stroke={axisColor} tick={{ fontSize: 11 }} />
            <YAxis stroke={axisColor} tick={{ fontSize: 11 }} tickFormatter={compactCurrency} domain={["auto", "auto"]} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#e8eef7" }} formatter={compactCurrency} />
            <Legend wrapperStyle={{ color: "#91a0b6", fontSize: 12 }} />
            {sampleKeys.map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke="#91a0b6"
                strokeOpacity={0.16}
                strokeWidth={1}
                dot={false}
                legendType="none"
                isAnimationActive={false}
              />
            ))}
            <Line type="monotone" dataKey="p5" stroke="#ff5c7a" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="p25" stroke="#f6b44b" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="p50" stroke="#38d2d2" strokeWidth={2.5} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="p75" stroke="#2dd47f" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="p95" stroke="#9b8cff" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function combineMonteCarlo(data?: MonteCarloChartType): CombinedPoint[] {
  const maxLength = Math.max(
    data?.p5?.length || 0,
    data?.p25?.length || 0,
    data?.p50?.length || 0,
    data?.p75?.length || 0,
    data?.p95?.length || 0,
  );

  return Array.from({ length: maxLength }, (_, index) => {
    const point: CombinedPoint = {
      day: data?.p50?.[index]?.day ?? index,
      p5: data?.p5?.[index]?.value,
      p25: data?.p25?.[index]?.value,
      p50: data?.p50?.[index]?.value,
      p75: data?.p75?.[index]?.value,
      p95: data?.p95?.[index]?.value,
    };

    data?.sample_paths?.slice(0, 6).forEach((path, pathIndex) => {
      point[`sample_${pathIndex}`] = path.values?.[index]?.value;
    });

    return point;
  });
}

function formatPct(value: number | undefined): string {
  return typeof value === "number" ? `${value.toFixed(2)}%` : "0.00%";
}
