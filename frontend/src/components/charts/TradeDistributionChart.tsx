import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type { BacktestResult } from "../../api/client";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import { asNumber } from "../../lib/numberFormatters";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type TradeDistributionChartProps = {
  result: BacktestResult;
};

function TradeDistributionChart({ result }: TradeDistributionChartProps) {
  const returns = useMemo(
    () =>
      (result.tables?.trades || [])
        .map((trade) => {
          const raw = asNumber(trade.return) ?? asNumber(trade.return_pct);
          if (raw === null) return null;
          return Math.abs(raw) <= 1 ? raw * 100 : raw;
        })
        .filter((value): value is number => value !== null),
    [result.tables?.trades],
  );

  return (
    <SectionCard title="Trade Return Distribution" subtitle={`${returns.length} trade outcomes`}>
      {returns.length ? (
        <Plot
          data={
            [
              {
                type: "histogram",
                x: returns,
                marker: { color: "rgba(141,150,255,0.52)", line: { color: quantTheme.benchmark, width: 1 } },
                hovertemplate: "Return %{x:.2f}%<br>Count %{y}<extra></extra>",
              },
            ] as never
          }
          layout={{
            ...plotlyLayoutDefaults,
            height: 280,
            xaxis: { ...plotlyLayoutDefaults.xaxis, ticksuffix: "%" },
          }}
          config={plotlyConfig}
          className="w-full"
          useResizeHandler
          style={{ width: "100%", height: "280px" }}
        />
      ) : (
        <EmptyState title="No trade distribution" message="Trade return fields were not available in this response." />
      )}
    </SectionCard>
  );
}

export default memo(TradeDistributionChart);
