import { memo, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { CorrelationRow, PortfolioResult } from "../../api/client";
import { quantTheme } from "../../lib/chartThemes";
import { asNumber } from "../../lib/numberFormatters";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type CorrelationHeatmapProps = {
  result: PortfolioResult;
};

function CorrelationHeatmap({ result }: CorrelationHeatmapProps) {
  const rows = result.charts?.correlation_matrix || [];
  const option = useMemo(() => buildOption(rows), [rows]);

  return (
    <SectionCard title="Correlation Matrix" subtitle={`${rows.length} assets`}>
      {rows.length ? (
        <ReactECharts option={option} style={{ height: 340, width: "100%" }} notMerge lazyUpdate />
      ) : (
        <EmptyState title="No correlation matrix" message="The artifact did not include correlation data." />
      )}
    </SectionCard>
  );
}

function buildOption(rows: CorrelationRow[]) {
  const symbols = rows.map((row) => row.symbol);
  const data: Array<[number, number, number]> = [];
  rows.forEach((row, yIndex) => {
    symbols.forEach((symbol, xIndex) => {
      data.push([xIndex, yIndex, asNumber(row[symbol]) ?? 0]);
    });
  });

  return {
    backgroundColor: quantTheme.panel,
    tooltip: {
      backgroundColor: quantTheme.panelElevated,
      borderColor: quantTheme.gridline,
      textStyle: { color: quantTheme.text },
      formatter: ({ value }: { value: [number, number, number] }) =>
        `${symbols[value[1]]} / ${symbols[value[0]]}<br/>${value[2].toFixed(2)}`,
    },
    grid: { left: 52, right: 20, top: 18, bottom: 42 },
    xAxis: {
      type: "category",
      data: symbols,
      axisLabel: { color: quantTheme.axis },
      axisLine: { lineStyle: { color: quantTheme.gridline } },
    },
    yAxis: {
      type: "category",
      data: symbols,
      axisLabel: { color: quantTheme.axis },
      axisLine: { lineStyle: { color: quantTheme.gridline } },
    },
    visualMap: {
      min: -1,
      max: 1,
      show: false,
      inRange: { color: ["#9a3d50", "#263347", "#1f8f67"] },
    },
    series: [
      {
        type: "heatmap",
        data,
        label: {
          show: true,
          color: quantTheme.text,
          formatter: ({ value }: { value: [number, number, number] }) => value[2].toFixed(2),
        },
      },
    ],
  };
}

export default memo(CorrelationHeatmap);
