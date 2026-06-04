import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type { PortfolioResult } from "../../api/client";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type PortfolioWeightsChartProps = {
  result: PortfolioResult;
};

function PortfolioWeightsChart({ result }: PortfolioWeightsChartProps) {
  const rows = useMemo(
    () =>
      Object.entries(result.weights || {})
        .map(([symbol, weight]) => ({ symbol, allocation: Number(weight) * 100 }))
        .sort((a, b) => b.allocation - a.allocation),
    [result.weights],
  );

  return (
    <SectionCard title="Optimal Weights" subtitle={`${rows.length} selected assets`}>
      {rows.length ? (
        <Plot
          data={
            [
              {
                type: "bar",
                x: rows.map((row) => row.symbol),
                y: rows.map((row) => row.allocation),
                marker: { color: quantTheme.strategy },
                hovertemplate: "%{x}<br>Allocation %{y:.2f}%<extra></extra>",
              },
            ] as never
          }
          layout={{
            ...plotlyLayoutDefaults,
            height: 300,
            yaxis: { ...plotlyLayoutDefaults.yaxis, ticksuffix: "%", rangemode: "tozero" },
          }}
          config={plotlyConfig}
          className="w-full"
          useResizeHandler
          style={{ width: "100%", height: "300px" }}
        />
      ) : (
        <EmptyState title="No weights returned" message="The optimizer response did not include allocation weights." />
      )}
    </SectionCard>
  );
}

export default memo(PortfolioWeightsChart);
