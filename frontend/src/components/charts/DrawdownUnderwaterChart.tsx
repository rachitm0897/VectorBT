import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type { BacktestResult } from "../../api/client";
import { toDrawdownSeries } from "../../lib/chartTransforms";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import SectionCard from "../layout/SectionCard";

type DrawdownUnderwaterChartProps = {
  result: BacktestResult;
};

function DrawdownUnderwaterChart({ result }: DrawdownUnderwaterChartProps) {
  const data = useMemo(
    () => toDrawdownSeries(result.charts?.drawdown_curve || [], result.charts?.equity_curve || []),
    [result.charts?.drawdown_curve, result.charts?.equity_curve],
  );
  const maxDrawdown = data.reduce((min, point) => Math.min(min, point.drawdown_pct), 0);
  const maxPoint = data.find((point) => point.drawdown_pct === maxDrawdown);

  return (
    <SectionCard title="Drawdown Underwater" subtitle={`Max drawdown ${maxDrawdown.toFixed(2)}%`}>
      <Plot
        data={
          [
            {
              type: "scatter",
              mode: "lines",
              name: "Drawdown",
              x: data.map((point) => point.time),
              y: data.map((point) => point.drawdown_pct),
              line: { color: quantTheme.negative, width: 1.5 },
              fill: "tozeroy",
              fillcolor: quantTheme.negativeSoft,
              hovertemplate: "%{x}<br>%{y:.2f}%<extra></extra>",
            },
            maxPoint
              ? {
                  type: "scatter",
                  mode: "markers",
                  name: "Max DD",
                  x: [maxPoint.time],
                  y: [maxPoint.drawdown_pct],
                  marker: { color: quantTheme.warning, size: 8 },
                  hovertemplate: "Max DD<br>%{x}<br>%{y:.2f}%<extra></extra>",
                }
              : undefined,
          ].filter(Boolean) as never
        }
        layout={{
          ...plotlyLayoutDefaults,
          height: 300,
          yaxis: { ...plotlyLayoutDefaults.yaxis, ticksuffix: "%", zeroline: true },
        }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "300px" }}
      />
    </SectionCard>
  );
}

export default memo(DrawdownUnderwaterChart);
