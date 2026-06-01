import { memo, useMemo, useState } from "react";
import Plot from "react-plotly.js";
import type { BacktestResult } from "../../api/client";
import { deriveRollingMetrics } from "../../lib/chartTransforms";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import SectionCard from "../layout/SectionCard";

type RollingMetricsChartProps = {
  result: BacktestResult;
};

const metricOptions = [
  { key: "rolling_return_pct", label: "Rolling Return", suffix: "%" },
  { key: "rolling_volatility_pct", label: "Rolling Volatility", suffix: "%" },
  { key: "rolling_sharpe", label: "Rolling Sharpe", suffix: "" },
  { key: "rolling_win_rate_pct", label: "Rolling Win Rate", suffix: "%" },
] as const;

function RollingMetricsChart({ result }: RollingMetricsChartProps) {
  const [metric, setMetric] = useState<(typeof metricOptions)[number]["key"]>("rolling_return_pct");
  const rows = useMemo(() => deriveRollingMetrics(result.charts?.equity_curve || []), [result.charts?.equity_curve]);
  const selected = metricOptions.find((option) => option.key === metric) || metricOptions[0];

  return (
    <SectionCard
      title="Rolling Analytics"
      subtitle="30-session derived metrics"
      action={
        <div className="flex flex-wrap gap-1">
          {metricOptions.map((option) => (
            <button
              key={option.key}
              className={`border px-2 py-1 text-[11px] uppercase tracking-[0.12em] ${
                metric === option.key ? "border-cyan text-cyan" : "border-line text-muted"
              }`}
              type="button"
              onClick={() => setMetric(option.key)}
            >
              {option.label.replace("Rolling ", "")}
            </button>
          ))}
        </div>
      }
    >
      <Plot
        data={
          [
            {
              type: "scatter",
              mode: "lines",
              name: selected.label,
              x: rows.map((row) => row.time),
              y: rows.map((row) => row[metric]),
              line: { color: quantTheme.strategy, width: 1.8 },
              hovertemplate: `%{x}<br>%{y:.2f}${selected.suffix}<extra></extra>`,
            },
          ] as never
        }
        layout={{
          ...plotlyLayoutDefaults,
          height: 300,
          yaxis: { ...plotlyLayoutDefaults.yaxis, ticksuffix: selected.suffix },
        }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "300px" }}
      />
    </SectionCard>
  );
}

export default memo(RollingMetricsChart);
