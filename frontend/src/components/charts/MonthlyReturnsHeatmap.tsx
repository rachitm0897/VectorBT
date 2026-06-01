import { memo, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { BacktestResult } from "../../api/client";
import { deriveMonthlyReturns } from "../../lib/chartTransforms";
import { quantTheme } from "../../lib/chartThemes";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type MonthlyReturnsHeatmapProps = {
  result: BacktestResult;
};

const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function MonthlyReturnsHeatmap({ result }: MonthlyReturnsHeatmapProps) {
  const monthly = useMemo(() => deriveMonthlyReturns(result.charts?.equity_curve || []), [result.charts?.equity_curve]);
  const years = Array.from(new Set(monthly.map((row) => row.year)));
  const data = monthly.map((row) => [row.month, years.indexOf(row.year), Number(row.return_pct.toFixed(2))]);

  return (
    <SectionCard title="Monthly Returns" subtitle="Derived from strategy equity">
      {monthly.length ? (
        <ReactECharts
          option={{
            backgroundColor: quantTheme.panel,
            tooltip: {
              backgroundColor: quantTheme.panelElevated,
              borderColor: quantTheme.gridline,
              textStyle: { color: quantTheme.text },
              formatter: (params: { value: [number, number, number] }) =>
                `${months[params.value[0]]} ${years[params.value[1]]}<br/>${params.value[2].toFixed(2)}%`,
            },
            grid: { left: 56, right: 20, top: 18, bottom: 35 },
            xAxis: { type: "category", data: months, axisLabel: { color: quantTheme.axis }, axisLine: { lineStyle: { color: quantTheme.gridline } } },
            yAxis: { type: "category", data: years, axisLabel: { color: quantTheme.axis }, axisLine: { lineStyle: { color: quantTheme.gridline } } },
            visualMap: { min: -12, max: 12, show: false, inRange: { color: ["#aa4355", "#263347", "#1d9b69"] } },
            series: [{ type: "heatmap", data, label: { show: true, color: quantTheme.text, fontSize: 10, formatter: ({ value }: { value: number[] }) => `${value[2].toFixed(1)}%` } }],
          }}
          style={{ height: 310, width: "100%" }}
          notMerge
          lazyUpdate
        />
      ) : (
        <EmptyState title="No monthly returns" message="Equity data is required to derive monthly returns." />
      )}
    </SectionCard>
  );
}

export default memo(MonthlyReturnsHeatmap);
