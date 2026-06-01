import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type { BacktestResult } from "../../api/client";
import { toMonteCarloBands } from "../../lib/chartTransforms";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import SectionCard from "../layout/SectionCard";

type MonteCarloFanChartProps = {
  result: BacktestResult;
};

function MonteCarloFanChart({ result }: MonteCarloFanChartProps) {
  const bands = useMemo(() => toMonteCarloBands(result.charts?.monte_carlo), [result.charts?.monte_carlo]);
  const sampleKeys = bands.length ? Object.keys(bands[0]).filter((key) => key.startsWith("sample_")).slice(0, 8) : [];
  const days = bands[bands.length - 1]?.day ?? 0;
  const simulations = result.request ? 500 : 0;

  const sampleTraces = sampleKeys.map((key) => ({
    type: "scatter",
    mode: "lines",
    name: key,
    x: bands.map((point) => point.day),
    y: bands.map((point) => point[key as `sample_${number}`]),
    line: { color: "rgba(139,153,173,0.18)", width: 1 },
    hoverinfo: "skip",
    showlegend: false,
  }));

  return (
    <SectionCard title="Monte Carlo Fan" subtitle={`${simulations} simulations / ${days} forward days`}>
      <Plot
        data={
          [
            ...sampleTraces,
            {
              type: "scatter",
              mode: "lines",
              name: "p95",
              x: bands.map((point) => point.day),
              y: bands.map((point) => point.p95),
              line: { width: 0, color: "transparent" },
              hoverinfo: "skip",
              showlegend: false,
            },
            {
              type: "scatter",
              mode: "lines",
              name: "p5-p95",
              x: bands.map((point) => point.day),
              y: bands.map((point) => point.p5),
              fill: "tonexty",
              fillcolor: quantTheme.mcOuter,
              line: { width: 0, color: "transparent" },
              hoverinfo: "skip",
              showlegend: false,
            },
            {
              type: "scatter",
              mode: "lines",
              name: "p75",
              x: bands.map((point) => point.day),
              y: bands.map((point) => point.p75),
              line: { width: 0, color: "transparent" },
              hoverinfo: "skip",
              showlegend: false,
            },
            {
              type: "scatter",
              mode: "lines",
              name: "p25-p75",
              x: bands.map((point) => point.day),
              y: bands.map((point) => point.p25),
              fill: "tonexty",
              fillcolor: quantTheme.mcInner,
              line: { width: 0, color: "transparent" },
              hoverinfo: "skip",
              showlegend: false,
            },
            {
              type: "scatter",
              mode: "lines",
              name: "Median",
              x: bands.map((point) => point.day),
              y: bands.map((point) => point.p50),
              line: { color: quantTheme.mcMedian, width: 2.2 },
              hovertemplate: "Day %{x}<br>Median %{y:$,.2f}<extra></extra>",
            },
          ] as never
        }
        layout={{
          ...plotlyLayoutDefaults,
          height: 340,
          yaxis: { ...plotlyLayoutDefaults.yaxis, tickprefix: "$" },
          xaxis: { ...plotlyLayoutDefaults.xaxis, title: { text: "Forward day", font: { color: quantTheme.axis, size: 11 } } },
        }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "340px" }}
      />
    </SectionCard>
  );
}

export default memo(MonteCarloFanChart);
