import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type { BacktestResult } from "../../api/client";
import { normalizeBenchmarkSeries } from "../../lib/chartTransforms";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import SectionCard from "../layout/SectionCard";

type EquityBenchmarkChartProps = {
  result: BacktestResult;
};

function EquityBenchmarkChart({ result }: EquityBenchmarkChartProps) {
  const data = useMemo(
    () => normalizeBenchmarkSeries(result.charts?.equity_curve || [], result.charts?.price || []),
    [result.charts?.equity_curve, result.charts?.price],
  );

  const traces = [
    {
      type: "scatter",
      mode: "lines",
      name: "Strategy",
      x: data.map((point) => point.time),
      y: data.map((point) => point.strategy),
      line: { color: quantTheme.strategy, width: 2 },
      hovertemplate: "%{x}<br>Strategy %{y:$,.2f}<extra></extra>",
    },
    {
      type: "scatter",
      mode: "lines",
      name: "Buy & Hold",
      x: data.map((point) => point.time),
      y: data.map((point) => point.buy_hold),
      line: { color: quantTheme.benchmark, width: 1.7 },
      hovertemplate: "%{x}<br>Buy & Hold %{y:$,.2f}<extra></extra>",
    },
    {
      type: "scatter",
      mode: "lines",
      name: "SPY",
      x: data.map((point) => point.time),
      y: data.map((point) => point.spy),
      line: { color: quantTheme.warning, width: 1.4, dash: "dot" },
      hovertemplate: "%{x}<br>SPY %{y:$,.2f}<extra></extra>",
      visible: data.some((point) => point.spy !== null) ? true : "legendonly",
    },
  ];

  return (
    <SectionCard title="Equity vs Benchmark" subtitle="Normalized portfolio value">
      <Plot
        data={traces as never}
        layout={{
          ...plotlyLayoutDefaults,
          height: 330,
          yaxis: { ...plotlyLayoutDefaults.yaxis, tickprefix: "$" },
        }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "330px" }}
      />
    </SectionCard>
  );
}

export default memo(EquityBenchmarkChart);
