import { useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";
import type {
  PortfolioResult,
  PortfolioScenarioAssumptions,
  PortfolioScenarioChart,
  PortfolioScenarioName,
  PortfolioScenarioSummary,
} from "../../api/client";
import { formatCurrency, formatNumber, formatPercent } from "../../lib/numberFormatters";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme, scenarioTheme } from "../../lib/chartThemes";
import SectionCard from "../layout/SectionCard";

type PortfolioScenarioAnalysisProps = {
  result: PortfolioResult;
};

const pathKeys = ["p5", "p25", "p50", "p75", "p95"] as const;

export default function PortfolioScenarioAnalysis({ result }: PortfolioScenarioAnalysisProps) {
  const scenarios = useMemo(() => normalizedScenarios(result), [result]);
  const [selectedScenario, setSelectedScenario] = useState<string>(scenarios[0]?.name || "");

  useEffect(() => {
    if (!scenarios.length) return;
    if (!scenarios.some((scenario) => scenario.name === selectedScenario)) {
      setSelectedScenario(scenarios[0].name);
    }
  }, [scenarios, selectedScenario]);

  if (!result.scenario_analysis?.enabled || !scenarios.length) return null;

  const charts = result.charts?.scenario_analysis || {};
  const selected = selectedScenario || scenarios[0]?.name || "";
  const selectedChart = charts[selected];
  const medianComparison = scenarios
    .map((scenario) => ({
      scenario,
      path: charts[scenario.name]?.percentile_paths?.p50 || [],
    }))
    .filter((item) => item.path.length > 0);

  return (
    <div className="space-y-4">
      <SectionCard
        title="Scenario Analysis"
        subtitle={scenarioSubtitle(result)}
      >
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-4">
          {scenarios.map((scenario) => (
            <ScenarioSummaryCard key={scenario.name} scenario={scenario} />
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Scenario Comparison" subtitle="portfolio-level Monte Carlo summaries">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-left text-xs">
            <thead className="text-[10px] uppercase tracking-[0.14em] text-muted">
              <tr>
                <th className="border-b border-line px-3 py-2">Scenario</th>
                <th className="border-b border-line px-3 py-2">Expected Return</th>
                <th className="border-b border-line px-3 py-2">Probability Positive</th>
                <th className="border-b border-line px-3 py-2">Probability Loss &gt; 10%</th>
                <th className="border-b border-line px-3 py-2">P5 Return</th>
                <th className="border-b border-line px-3 py-2">Median Return</th>
                <th className="border-b border-line px-3 py-2">P95 Return</th>
                <th className="border-b border-line px-3 py-2">Average Max Drawdown</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((scenario) => (
                <tr key={scenario.name} className="border-b border-line/70 last:border-b-0">
                  <td className="px-3 py-2 font-semibold" style={{ color: scenarioColor(scenario.name) }}>
                    {scenario.label}
                  </td>
                  <td className="px-3 py-2">{formatPercent(scenario.summary?.expected_return_pct)}</td>
                  <td className="px-3 py-2">{formatPercent(scenario.summary?.probability_positive_return_pct)}</td>
                  <td className="px-3 py-2">{formatPercent(scenario.summary?.probability_loss_above_10_pct)}</td>
                  <td className="px-3 py-2">{formatPercent(scenario.summary?.p5_return_pct)}</td>
                  <td className="px-3 py-2">{formatPercent(scenario.summary?.p50_return_pct)}</td>
                  <td className="px-3 py-2">{formatPercent(scenario.summary?.p95_return_pct)}</td>
                  <td className="px-3 py-2">{formatDrawdownPct(scenario.summary?.average_max_drawdown_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <ScenarioFanChart
          chart={selectedChart}
          selectedScenario={selected}
          scenarios={scenarios}
          onSelect={setSelectedScenario}
        />
        <ScenarioAssumptionsPanel scenarios={scenarios} />
      </div>

      <SectionCard title="Median Scenario Comparison" subtitle="P50 path by scenario">
        {medianComparison.length ? (
          <Plot
            data={
              medianComparison.map(({ scenario, path }) => ({
                type: "scatter",
                mode: "lines",
                name: scenario.label,
                x: path.map((_, index) => index),
                y: path,
                line: { color: scenarioColor(scenario.name), width: 2.2 },
              hovertemplate: "Simulation Day %{x}<br>%{y:$,.2f}<extra></extra>",
              })) as never
            }
            layout={{
              ...plotlyLayoutDefaults,
              height: 320,
              yaxis: {
                ...plotlyLayoutDefaults.yaxis,
                tickprefix: "$",
                title: { text: "Portfolio Value", font: { color: quantTheme.axis, size: 11 } },
              },
              xaxis: {
                ...plotlyLayoutDefaults.xaxis,
                title: { text: "Simulation Day", font: { color: quantTheme.axis, size: 11 } },
              },
            }}
            config={plotlyConfig}
            className="w-full"
            useResizeHandler
            style={{ width: "100%", height: "320px" }}
          />
        ) : (
          <EmptyScenarioChart />
        )}
      </SectionCard>
    </div>
  );
}

function ScenarioSummaryCard({ scenario }: { scenario: NormalizedScenario }) {
  const summary = scenario.summary || {};
  return (
    <div className="border bg-ink p-3" style={{ borderColor: scenarioColor(scenario.name) }}>
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: scenarioColor(scenario.name) }}>
        {scenario.label}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <Metric label="Expected" value={formatPercent(summary.expected_return_pct)} />
        <Metric label="Positive" value={formatPercent(summary.probability_positive_return_pct)} />
        <Metric label="Loss > 10%" value={formatPercent(summary.probability_loss_above_10_pct)} />
        <Metric label="P5" value={formatPercent(summary.p5_return_pct)} />
        <Metric label="Median" value={formatPercent(summary.p50_return_pct)} />
        <Metric label="P95" value={formatPercent(summary.p95_return_pct)} />
        <Metric label="Avg Drawdown" value={formatDrawdownPct(summary.average_max_drawdown_pct)} />
        <Metric label="Expected Value" value={formatCurrency(summary.expected_final_value)} />
      </div>
    </div>
  );
}

function ScenarioFanChart({
  chart,
  selectedScenario,
  scenarios,
  onSelect,
}: {
  chart?: PortfolioScenarioChart;
  selectedScenario: string;
  scenarios: NormalizedScenario[];
  onSelect: (scenario: string) => void;
}) {
  const [showSamples, setShowSamples] = useState(false);
  const paths = chart?.percentile_paths || {};
  const hasPaths = pathKeys.some((key) => (paths[key] || []).length > 0);
  const x = Array.from({ length: Math.max(...pathKeys.map((key) => paths[key]?.length || 0), 0) }, (_, index) => index);
  const sampleTraces = showSamples ? (chart?.sample_paths || []).slice(0, 8).map((path, index) => ({
    type: "scatter",
    mode: "lines",
    name: `sample_${index}`,
    x: path.map((_, day) => day),
    y: path,
    line: { color: "rgba(139,153,173,0.18)", width: 1 },
    hoverinfo: "skip",
    showlegend: false,
  })) : [];
  const startValue = firstPathValue(paths);

  return (
    <SectionCard
      title="Scenario Fan Chart"
      subtitle={`${scenarioLabel(selectedScenario)} / starts ${formatCurrency(startValue)}`}
      action={
        <div className="flex items-center gap-2">
          <button
            className="border border-line px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted transition hover:border-cyan hover:text-cyan"
            type="button"
            onClick={() => setShowSamples((current) => !current)}
          >
            {showSamples ? "Hide Samples" : "Show Samples"}
          </button>
          <select
            className="border border-line bg-ink px-2 py-1 text-xs text-text"
            value={selectedScenario}
            onChange={(event) => onSelect(event.target.value)}
          >
            {scenarios.map((scenario) => (
              <option key={scenario.name} value={scenario.name}>
                {scenario.label}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {hasPaths ? (
        <Plot
          data={
            [
              ...sampleTraces,
              {
                type: "scatter",
                mode: "lines",
                name: "p95",
                x,
                y: paths.p95 || [],
                line: { width: 0, color: "transparent" },
                hoverinfo: "skip",
                showlegend: false,
              },
              {
                type: "scatter",
                mode: "lines",
                name: "P5-P95",
                x,
                y: paths.p5 || [],
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
                x,
                y: paths.p75 || [],
                line: { width: 0, color: "transparent" },
                hoverinfo: "skip",
                showlegend: false,
              },
              {
                type: "scatter",
                mode: "lines",
                name: "P25-P75",
                x,
                y: paths.p25 || [],
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
                x,
                y: paths.p50 || [],
                line: { color: scenarioColor(selectedScenario), width: 2.4 },
                hovertemplate: "Simulation Day %{x}<br>Median %{y:$,.2f}<extra></extra>",
              },
            ] as never
          }
          layout={{
            ...plotlyLayoutDefaults,
            height: 340,
            yaxis: {
              ...plotlyLayoutDefaults.yaxis,
              tickprefix: "$",
              title: { text: "Portfolio Value", font: { color: quantTheme.axis, size: 11 } },
            },
            xaxis: {
              ...plotlyLayoutDefaults.xaxis,
              title: { text: "Simulation Day", font: { color: quantTheme.axis, size: 11 } },
            },
          }}
          config={plotlyConfig}
          className="w-full"
          useResizeHandler
          style={{ width: "100%", height: "340px" }}
        />
      ) : (
        <EmptyScenarioChart />
      )}
    </SectionCard>
  );
}

function ScenarioAssumptionsPanel({ scenarios }: { scenarios: NormalizedScenario[] }) {
  return (
    <SectionCard title="Assumptions" subtitle="scenario inputs used">
      <div className="space-y-3">
        {scenarios.map((scenario) => (
          <div key={scenario.name} className="border border-line bg-ink p-3">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: scenarioColor(scenario.name) }}>
              {scenario.label}
            </div>
            <Metric label="Drift Adjustment" value={formatAssumptionPct(scenario.assumptions?.drift_shift_annual)} />
            <Metric label="Volatility Multiplier" value={formatMultiplier(scenario.assumptions?.volatility_multiplier)} />
            <Metric label="Initial Shock" value={formatAssumptionPct(scenario.assumptions?.initial_shock_pct)} />
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border border-line/70 bg-panel px-2 py-1.5">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</span>
      <span className="text-right font-mono text-xs text-text">{value}</span>
    </div>
  );
}

function EmptyScenarioChart() {
  return (
    <div className="flex min-h-64 items-center justify-center border border-dashed border-line bg-ink px-4 text-center text-xs uppercase tracking-[0.14em] text-muted">
      Scenario chart artifact is unavailable. Compact scenario summaries are still shown.
    </div>
  );
}

type NormalizedScenario = {
  name: string;
  label: string;
  assumptions?: PortfolioScenarioAssumptions;
  summary?: PortfolioScenarioSummary;
};

function normalizedScenarios(result: PortfolioResult): NormalizedScenario[] {
  const compact = result.scenario_analysis?.scenarios || [];
  const charts = result.charts?.scenario_analysis || {};
  const names = new Set<string>();
  compact.forEach((scenario) => names.add(String(scenario.name)));
  Object.keys(charts).forEach((name) => names.add(name));

  return Array.from(names)
    .map((name) => {
      const compactScenario = compact.find((scenario) => scenario.name === name);
      const chartScenario = charts[name];
      return {
        name,
        label: compactScenario?.label || scenarioLabel(name),
        assumptions: compactScenario?.assumptions || chartScenario?.assumptions,
        summary: compactScenario?.summary || chartScenario?.summary,
      };
    })
    .sort((left, right) => scenarioOrder(left.name) - scenarioOrder(right.name));
}

function scenarioSubtitle(result: PortfolioResult): string {
  const config = result.scenario_analysis?.config || {};
  const days = config.days ?? 60;
  const simulations = config.simulations ?? 500;
  const blockSize = config.block_size ?? 5;
  const start = config.portfolio_start_value ? ` / starts ${formatCurrency(config.portfolio_start_value)}` : "";
  return `${simulations} simulations / ${days} days / ${blockSize}-day blocks${start}`;
}

function scenarioColor(name: string): string {
  const key = name as PortfolioScenarioName;
  return scenarioTheme[key] || quantTheme.neutral;
}

function scenarioLabel(name: string): string {
  return {
    neutral: "Neutral",
    bullish: "Bullish",
    bearish: "Bearish",
    crash: "Crash",
  }[name] || name.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function scenarioOrder(name: string): number {
  return ["neutral", "bullish", "bearish", "crash"].indexOf(name) === -1
    ? 99
    : ["neutral", "bullish", "bearish", "crash"].indexOf(name);
}

function formatAssumptionPct(value: unknown): string {
  const parsed = typeof value === "number" && Number.isFinite(value) ? value : null;
  return parsed === null ? "-" : `${(parsed * 100).toFixed(2)}%`;
}

function formatMultiplier(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? `${formatNumber(value)}x` : "-";
}

function formatDrawdownPct(value: unknown): string {
  const parsed = typeof value === "number" && Number.isFinite(value) ? value : null;
  return parsed === null ? "-" : formatPercent(-Math.abs(parsed), 1);
}

function firstPathValue(paths: PortfolioScenarioChart["percentile_paths"] | undefined): number | null {
  for (const key of pathKeys) {
    const value = paths?.[key]?.[0];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}
