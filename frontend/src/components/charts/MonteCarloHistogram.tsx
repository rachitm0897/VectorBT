import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type { BacktestResult } from "../../api/client";
import { deriveMonteCarloFinalReturns } from "../../lib/chartTransforms";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import { formatPercent } from "../../lib/numberFormatters";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type MonteCarloHistogramProps = {
  result: BacktestResult;
};

function MonteCarloHistogram({ result }: MonteCarloHistogramProps) {
  const finalReturns = useMemo(() => deriveMonteCarloFinalReturns(result.charts?.monte_carlo), [result.charts?.monte_carlo]);
  const median = finalReturns.length ? [...finalReturns].sort((a, b) => a - b)[Math.floor(finalReturns.length / 2)] : null;
  const positiveProbability = result.summary?.probability_positive_return_pct;

  return (
    <SectionCard
      title="Final Return Distribution"
      subtitle={`Positive probability ${formatPercent(positiveProbability)}`}
    >
      {finalReturns.length ? (
        <Plot
          data={
            [
              {
                type: "histogram",
                name: "Final returns",
                x: finalReturns,
                marker: { color: "rgba(50,211,211,0.58)", line: { color: quantTheme.strategy, width: 1 } },
                hovertemplate: "Return %{x:.2f}%<br>Count %{y}<extra></extra>",
              },
            ] as never
          }
          layout={{
            ...plotlyLayoutDefaults,
            height: 280,
            bargap: 0.04,
            shapes: [
              { type: "line", x0: 0, x1: 0, y0: 0, y1: 1, yref: "paper", line: { color: quantTheme.neutral, dash: "dot" } },
              median !== null
                ? { type: "line", x0: median, x1: median, y0: 0, y1: 1, yref: "paper", line: { color: quantTheme.warning } }
                : undefined,
            ].filter(Boolean),
            xaxis: { ...plotlyLayoutDefaults.xaxis, ticksuffix: "%" },
          }}
          config={plotlyConfig}
          className="w-full"
          useResizeHandler
          style={{ width: "100%", height: "280px" }}
        />
      ) : (
        <EmptyState title="No distribution" message="Monte Carlo sample paths were not available for a final-return histogram." />
      )}
    </SectionCard>
  );
}

export default memo(MonteCarloHistogram);
