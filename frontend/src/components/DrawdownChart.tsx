import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EquityPoint } from "../api/client";
import { axisColor, chartGrid, compactNumber, tooltipStyle } from "./chartUtils";

type DrawdownChartProps = {
  data?: EquityPoint[];
};

export default function DrawdownChart({ data = [] }: DrawdownChartProps) {
  return (
    <section className="panel-shell p-4">
      <div className="mb-3 flex items-center justify-between border-b border-line pb-3">
        <h2 className="section-title">Drawdown</h2>
        <span className="text-xs text-muted">{data.length} points</span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={chartGrid} strokeDasharray="3 3" />
            <XAxis dataKey="date" stroke={axisColor} tick={{ fontSize: 11 }} minTickGap={32} />
            <YAxis stroke={axisColor} tick={{ fontSize: 11 }} tickFormatter={(value) => `${compactNumber(value)}%`} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: "#e8eef7" }}
              formatter={(value) => [`${compactNumber(value)}%`, "Drawdown"]}
            />
            <Line
              type="monotone"
              dataKey="drawdown_pct"
              stroke="#ff5c7a"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
