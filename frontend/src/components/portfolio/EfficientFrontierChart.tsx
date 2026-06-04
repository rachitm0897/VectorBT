import { memo, useMemo } from "react";
import Plot from "react-plotly.js";
import type {
  IndividualAssetPoint,
  OptimalPortfolioPoint,
  PortfolioChartPoint,
  PortfolioResult,
  RandomPortfolioPoint,
} from "../../api/client";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

type EfficientFrontierChartProps = {
  result: PortfolioResult;
};

type NormalizedPoint = {
  volatility: number;
  portfolioReturn: number;
  sharpe: number;
  ticker?: string;
  weights?: Record<string, number>;
};

function EfficientFrontierChart({ result }: EfficientFrontierChartProps) {
  const charts = result.charts || {};
  const chartData = useMemo(() => {
    const randomPortfolios = normalizePoints(charts.random_portfolios || []);
    const frontier = normalizePoints(charts.efficient_frontier || []);
    const individualAssets = normalizePoints(charts.individual_assets || [], true);
    const minVolatility = normalizePoint(charts.min_volatility_portfolio);
    const maxSharpe = normalizePoint(charts.max_sharpe_portfolio);
    const selected =
      result.objective === "min_volatility"
        ? minVolatility || fallbackSelectedPoint(result)
        : maxSharpe || fallbackSelectedPoint(result);

    return { randomPortfolios, frontier, individualAssets, minVolatility, maxSharpe, selected };
  }, [
    charts.efficient_frontier,
    charts.individual_assets,
    charts.max_sharpe_portfolio,
    charts.min_volatility_portfolio,
    charts.random_portfolios,
    result,
  ]);

  const hasPlotData =
    chartData.randomPortfolios.length > 0 ||
    chartData.frontier.length > 0 ||
    Boolean(chartData.minVolatility) ||
    Boolean(chartData.maxSharpe);
  const traces = useMemo(() => buildTraces(chartData), [chartData]);
  const annotations = useMemo(() => buildAnnotations(chartData), [chartData]);

  return (
    <SectionCard title="Efficient Frontier: Risk vs Return" subtitle={`${chartData.randomPortfolios.length} random portfolios`}>
      <div className="space-y-4">
        {hasPlotData ? (
          <Plot
            data={traces as never}
            layout={{
              ...plotlyLayoutDefaults,
              title: { text: "Efficient Frontier: Risk vs Return", font: { color: quantTheme.text, size: 15 } },
              height: 460,
              margin: { l: 64, r: 82, t: 48, b: 58 },
              xaxis: {
                ...plotlyLayoutDefaults.xaxis,
                type: "linear",
                title: { text: "Annualized Volatility (%)", font: { color: quantTheme.axis, size: 12 } },
                tickformat: ".0%",
                tickangle: 0,
                automargin: true,
                gridcolor: "rgba(255,255,255,0.08)",
                zeroline: false,
              },
              yaxis: {
                ...plotlyLayoutDefaults.yaxis,
                type: "linear",
                title: { text: "Annualized Expected Return (%)", font: { color: quantTheme.axis, size: 12 } },
                tickformat: ".0%",
                tickangle: 0,
                automargin: true,
                gridcolor: "rgba(255,255,255,0.08)",
                zeroline: false,
              },
              legend: {
                ...plotlyLayoutDefaults.legend,
                x: 0,
                y: 1.12,
                bgcolor: "rgba(11,17,25,0.7)",
              },
              annotations,
            }}
            config={plotlyConfig}
            className="w-full"
            useResizeHandler
            style={{ width: "100%", height: "460px" }}
          />
        ) : (
          <EmptyState title="No frontier data" message="Run optimization again to populate random portfolios and frontier data." />
        )}

        <SelectedPortfolioDetails selected={chartData.selected} objective={result.objective} />
      </div>
    </SectionCard>
  );
}

function buildTraces(chartData: {
  randomPortfolios: NormalizedPoint[];
  frontier: NormalizedPoint[];
  individualAssets: NormalizedPoint[];
  minVolatility: NormalizedPoint | null;
  maxSharpe: NormalizedPoint | null;
}) {
  const traces: Array<Record<string, unknown>> = [];

  if (chartData.randomPortfolios.length) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Random Portfolios",
      x: chartData.randomPortfolios.map((point) => point.volatility),
      y: chartData.randomPortfolios.map((point) => point.portfolioReturn),
      marker: {
        color: chartData.randomPortfolios.map((point) => point.sharpe),
        colorscale: "Viridis",
        showscale: true,
        size: 5,
        opacity: 0.42,
        colorbar: {
          title: { text: "Sharpe Ratio", font: { color: quantTheme.axis, size: 11 } },
          tickfont: { color: quantTheme.axis },
        },
      },
      customdata: chartData.randomPortfolios.map((point) => point.sharpe),
      hovertemplate: "Vol %{x:.1%}<br>Return %{y:.1%}<br>Sharpe %{customdata:.2f}<extra></extra>",
    });
  }

  if (chartData.frontier.length) {
    traces.push({
      type: "scatter",
      mode: "lines",
      name: "Efficient Frontier",
      x: chartData.frontier.map((point) => point.volatility),
      y: chartData.frontier.map((point) => point.portfolioReturn),
      line: { color: quantTheme.warning, width: 4, shape: "spline", smoothing: 0.55 },
      hovertemplate: "Frontier<br>Vol %{x:.1%}<br>Return %{y:.1%}<br>Sharpe %{customdata:.2f}<extra></extra>",
      customdata: chartData.frontier.map((point) => point.sharpe),
    });
  }

  if (chartData.minVolatility) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Minimum Volatility",
      x: [chartData.minVolatility.volatility],
      y: [chartData.minVolatility.portfolioReturn],
      marker: { color: quantTheme.positive, size: 16, symbol: "circle", line: { color: quantTheme.text, width: 2 } },
      cliponaxis: false,
      hovertemplate: "Minimum Volatility<br>Vol %{x:.1%}<br>Return %{y:.1%}<br>Sharpe %{customdata:.2f}<extra></extra>",
      customdata: [chartData.minVolatility.sharpe],
    });
  }

  if (chartData.maxSharpe) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Maximum Sharpe",
      x: [chartData.maxSharpe.volatility],
      y: [chartData.maxSharpe.portfolioReturn],
      marker: { color: quantTheme.strategy, size: 19, symbol: "star", line: { color: quantTheme.text, width: 2 } },
      cliponaxis: false,
      hovertemplate: "Maximum Sharpe<br>Vol %{x:.1%}<br>Return %{y:.1%}<br>Sharpe %{customdata:.2f}<extra></extra>",
      customdata: [chartData.maxSharpe.sharpe],
    });
  }

  if (chartData.individualAssets.length) {
    const showLabels = chartData.individualAssets.length <= 12;
    traces.push({
      type: "scatter",
      mode: showLabels ? "markers+text" : "markers",
      name: "Individual Assets",
      x: chartData.individualAssets.map((point) => point.volatility),
      y: chartData.individualAssets.map((point) => point.portfolioReturn),
      text: chartData.individualAssets.map((point) => point.ticker || ""),
      textposition: "top center",
      textfont: { color: quantTheme.text, size: 10 },
      marker: { color: "#05080d", size: 8, line: { color: quantTheme.muted, width: 1 } },
      hovertemplate: "%{text}<br>Vol %{x:.1%}<br>Return %{y:.1%}<br>Sharpe %{customdata:.2f}<extra></extra>",
      customdata: chartData.individualAssets.map((point) => point.sharpe),
    });
  }

  return traces;
}

function buildAnnotations(chartData: {
  minVolatility: NormalizedPoint | null;
  maxSharpe: NormalizedPoint | null;
}) {
  const annotations: Array<Record<string, unknown>> = [];
  if (chartData.minVolatility) {
    annotations.push(markerAnnotation("Minimum Volatility", chartData.minVolatility, -42, 42));
  }
  if (chartData.maxSharpe) {
    annotations.push(markerAnnotation("Maximum Sharpe", chartData.maxSharpe, 42, -42));
  }
  return annotations;
}

function markerAnnotation(label: string, point: NormalizedPoint, ax: number, ay: number) {
  return {
    x: point.volatility,
    y: point.portfolioReturn,
    xref: "x",
    yref: "y",
    text: `${label}<br>Ret: ${formatPercentDecimal(point.portfolioReturn)}<br>Vol: ${formatPercentDecimal(point.volatility)}<br>Sharpe: ${point.sharpe.toFixed(2)}`,
    showarrow: true,
    arrowhead: 2,
    ax,
    ay,
    bgcolor: "rgba(11,17,25,0.9)",
    bordercolor: quantTheme.gridline,
    borderwidth: 1,
    font: { color: quantTheme.text, size: 11 },
  };
}

function SelectedPortfolioDetails({ selected, objective }: { selected: NormalizedPoint | null; objective?: string }) {
  if (!selected) return null;
  const title = objective === "min_volatility" ? "Selected Minimum Volatility Portfolio" : "Selected Maximum Sharpe Portfolio";
  return (
    <div className="border border-line bg-ink p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">{title}</div>
        <div className="grid grid-cols-3 gap-2 text-xs">
          <Metric label="Expected Annual Return" value={formatPercentDecimal(selected.portfolioReturn)} />
          <Metric label="Annual Volatility" value={formatPercentDecimal(selected.volatility)} />
          <Metric label="Sharpe Ratio" value={selected.sharpe.toFixed(2)} />
        </div>
      </div>
      {selected.weights ? (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {Object.entries(selected.weights).map(([symbol, weight]) => (
            <div key={symbol} className="flex items-center justify-between gap-2 border border-line bg-panel px-3 py-2 text-xs">
              <span className="font-mono text-text">{symbol}</span>
              <span className="font-mono text-cyan">{formatPercentDecimal(weight)}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-24 border border-line bg-panel px-3 py-2 text-right">
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="mt-1 font-mono text-text">{value}</div>
    </div>
  );
}

function normalizePoints(points: Array<PortfolioChartPoint | IndividualAssetPoint | RandomPortfolioPoint>, includeTicker = false): NormalizedPoint[] {
  return points
    .map((point) => normalizePoint(point, includeTicker))
    .filter((point): point is NormalizedPoint => point !== null);
}

function normalizePoint(point: PortfolioChartPoint | IndividualAssetPoint | RandomPortfolioPoint | OptimalPortfolioPoint | undefined, includeTicker = false): NormalizedPoint | null {
  if (!point) return null;
  const volatility = asFiniteNumber(point.portfolio_volatility) ?? percentToDecimal(point.annual_volatility_pct);
  const portfolioReturn = asFiniteNumber(point.portfolio_return) ?? percentToDecimal(point.expected_annual_return_pct);
  const sharpe = asFiniteNumber(point.sharpe_ratio) ?? 0;
  if (volatility === null || portfolioReturn === null) return null;
  return {
    volatility,
    portfolioReturn,
    sharpe,
    ticker: includeTicker && "ticker" in point ? point.ticker : undefined,
    weights: "weights" in point ? normalizeWeights(point.weights) : undefined,
  };
}

function fallbackSelectedPoint(result: PortfolioResult): NormalizedPoint | null {
  const metrics = result.metrics || {};
  const volatility = percentToDecimal(metrics.annual_volatility_pct);
  const portfolioReturn = percentToDecimal(metrics.expected_annual_return_pct);
  const sharpe = asFiniteNumber(metrics.sharpe_ratio) ?? 0;
  if (volatility === null || portfolioReturn === null) return null;
  return {
    volatility,
    portfolioReturn,
    sharpe,
    weights: normalizeWeights(result.weights),
  };
}

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function normalizeWeights(weights: unknown): Record<string, number> | undefined {
  if (!weights || typeof weights !== "object" || Array.isArray(weights)) return undefined;
  const normalized: Record<string, number> = {};
  for (const [symbol, weight] of Object.entries(weights)) {
    const parsed = asFiniteNumber(weight);
    if (parsed !== null) {
      normalized[symbol] = parsed;
    }
  }
  return Object.keys(normalized).length ? normalized : undefined;
}

function percentToDecimal(value: unknown): number | null {
  const parsed = asFiniteNumber(value);
  return parsed === null ? null : parsed / 100;
}

function formatPercentDecimal(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default memo(EfficientFrontierChart);
