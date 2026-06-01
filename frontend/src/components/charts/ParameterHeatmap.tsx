import { memo, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { BacktestResult } from "../../api/client";
import { quantTheme } from "../../lib/chartThemes";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type ParameterHeatmapProps = {
  result: BacktestResult;
};

const metrics = ["total_return_pct", "sharpe_ratio", "max_drawdown_pct", "win_rate_pct"];

function ParameterHeatmap({ result }: ParameterHeatmapProps) {
  const [metric, setMetric] = useState(metrics[0]);
  const sweep = result.charts?.parameter_sweep || [];
  const option = useMemo(() => buildOption(sweep, metric), [sweep, metric]);

  return (
    <SectionCard
      title="Parameter Surface"
      subtitle="Sweep matrix"
      action={
        <select className="border border-line bg-ink px-2 py-1 text-xs text-text" value={metric} onChange={(e) => setMetric(e.target.value)}>
          {metrics.map((item) => (
            <option key={item} value={item}>
              {item.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      }
    >
      {sweep.length ? (
        <ReactECharts option={option} style={{ height: 340, width: "100%" }} notMerge lazyUpdate />
      ) : (
        <EmptyState title="Run a parameter sweep to populate this heatmap." message="The current backend does not return sweep matrices yet." />
      )}
    </SectionCard>
  );
}

function buildOption(rows: Array<Record<string, unknown>>, metric: string) {
  const xValues = Array.from(new Set(rows.map((row) => String(row.x ?? row.fast_window ?? row.window ?? ""))));
  const yValues = Array.from(new Set(rows.map((row) => String(row.y ?? row.slow_window ?? row.std_dev ?? ""))));
  const data = rows.map((row) => [
    xValues.indexOf(String(row.x ?? row.fast_window ?? row.window ?? "")),
    yValues.indexOf(String(row.y ?? row.slow_window ?? row.std_dev ?? "")),
    Number(row[metric] ?? 0),
  ]);
  return {
    backgroundColor: quantTheme.panel,
    tooltip: { backgroundColor: quantTheme.panelElevated, borderColor: quantTheme.gridline, textStyle: { color: quantTheme.text } },
    grid: { left: 42, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: xValues, axisLabel: { color: quantTheme.axis }, axisLine: { lineStyle: { color: quantTheme.gridline } } },
    yAxis: { type: "category", data: yValues, axisLabel: { color: quantTheme.axis }, axisLine: { lineStyle: { color: quantTheme.gridline } } },
    visualMap: {
      min: Math.min(...data.map((item) => item[2] as number), 0),
      max: Math.max(...data.map((item) => item[2] as number), 1),
      show: false,
      inRange: { color: ["#9a3d50", "#263347", "#1f8f67"] },
    },
    series: [{ type: "heatmap", data, label: { show: true, color: quantTheme.text, formatter: ({ value }: { value: number[] }) => value[2].toFixed(1) } }],
  };
}

export default memo(ParameterHeatmap);
