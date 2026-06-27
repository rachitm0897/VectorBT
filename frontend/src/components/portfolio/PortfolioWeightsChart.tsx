import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type { PortfolioResult } from "../../api/client";
import { formatPercent } from "../../lib/numberFormatters";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import { toPortfolioWeightRows, totalWeightPct, weightTotalIsApprox100 } from "../../lib/portfolioViewModel";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type PortfolioWeightsChartProps = {
  result: PortfolioResult;
};

function PortfolioWeightsChart({ result }: PortfolioWeightsChartProps) {
  const rows = useMemo(() => toPortfolioWeightRows(result), [result]);
  const total = totalWeightPct(rows);
  const height = Math.max(300, rows.length * 34 + 96);

  return (
    <SectionCard title="Optimal Weights" subtitle={`${rows.length} selected assets / total ${formatPercent(total, 1)}`}>
      {rows.length ? (
        <>
          {!weightTotalIsApprox100(total) ? (
            <div className="mb-3 border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
              Portfolio weights total {formatPercent(total, 1)}; expected approximately 100%.
            </div>
          ) : null}
          <Plot
            data={
              [
                {
                  type: "bar",
                  orientation: "h",
                  x: rows.map((row) => row.weightPct),
                  y: rows.map((row) => row.symbol),
                  text: rows.map((row) => formatPercent(row.weightPct, 1)),
                  textposition: "auto",
                  cliponaxis: false,
                  marker: {
                    color: rows.map((_, index) => (index === 0 ? quantTheme.strategy : quantTheme.benchmark)),
                    line: { color: "rgba(230, 237, 247, 0.24)", width: 1 },
                  },
                  hovertemplate: "Stock %{y}<br>Weight %{x:.2f}%<extra></extra>",
                },
              ] as never
            }
            layout={{
              ...plotlyLayoutDefaults,
              height,
              margin: { l: 78, r: 54, t: 18, b: 52 },
              xaxis: {
                ...plotlyLayoutDefaults.xaxis,
                title: { text: "Weight (%)", font: { color: quantTheme.axis, size: 12 } },
                ticksuffix: "%",
                rangemode: "tozero",
                gridcolor: "rgba(255,255,255,0.08)",
                zeroline: false,
              },
              yaxis: {
                ...plotlyLayoutDefaults.yaxis,
                title: { text: "Stock", font: { color: quantTheme.axis, size: 12 } },
                categoryorder: "array",
                categoryarray: rows.map((row) => row.symbol),
                autorange: "reversed",
                automargin: true,
                gridcolor: "rgba(255,255,255,0.04)",
              },
              showlegend: false,
            }}
            config={plotlyConfig}
            className="w-full"
            useResizeHandler
            style={{ width: "100%", height: `${height}px` }}
          />
        </>
      ) : (
        <EmptyState title="No weights returned" message="The optimizer response did not include allocation weights." />
      )}
    </SectionCard>
  );
}

export default memo(PortfolioWeightsChart);
