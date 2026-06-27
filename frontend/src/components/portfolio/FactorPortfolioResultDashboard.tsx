import { useMemo, useState } from "react";
import Plot from "react-plotly.js";
import type { FactorPortfolioResult, FactorScoreRow, PortfolioResult } from "../../api/client";
import { formatNumber, formatPercent } from "../../lib/numberFormatters";
import { plotlyConfig, plotlyLayoutDefaults, quantTheme } from "../../lib/chartThemes";
import EmptyState from "../layout/EmptyState";
import ErrorState from "../layout/ErrorState";
import LoadingState from "../layout/LoadingState";
import SectionCard from "../layout/SectionCard";
import PortfolioScenarioAnalysis from "./PortfolioScenarioAnalysis";

type FactorPortfolioResultDashboardProps = {
  result: FactorPortfolioResult | null;
  isLoading: boolean;
  error: string | null;
};

export default function FactorPortfolioResultDashboard({ result, isLoading, error }: FactorPortfolioResultDashboardProps) {
  const [search, setSearch] = useState("");
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [sectorFilter, setSectorFilter] = useState("");
  const [scoreThreshold, setScoreThreshold] = useState(0);
  const [activeTicker, setActiveTicker] = useState<string | null>(null);

  const rows = useMemo(() => [...(result?.factor_scores || [])].sort((a, b) => (b.combined_portfolio_score || 0) - (a.combined_portfolio_score || 0)), [result]);
  const filteredRows = rows.filter((row) => {
    const query = search.trim().toUpperCase();
    if (query && ![row.ticker, row.company_name, row.sector].join(" ").toUpperCase().includes(query)) return false;
    if (selectedOnly && row.selection_status !== "selected") return false;
    if (sectorFilter && row.sector !== sectorFilter) return false;
    if ((row.combined_portfolio_score || 0) < scoreThreshold) return false;
    return true;
  });
  const sectors = Array.from(new Set(rows.map((row) => row.sector).filter(Boolean))) as string[];
  const active = rows.find((row) => row.ticker === activeTicker) || rows[0];

  if (isLoading) return <LoadingState label="Constructing factor portfolio" />;
  if (error && !result) return <ErrorState message={error} />;
  if (!result) {
    return <EmptyState title="No factor portfolio loaded" message="Configure a factor model, select a universe, and construct a portfolio." />;
  }

  const selected = result.selected_stocks || [];
  const metrics = result.optimization_result?.metrics || {};
  const averageScore = average(selected.map((item) => item.combined_portfolio_score));
  const averageCoverage = average(selected.map((item) => item.data_coverage_pct));

  return (
    <div className="space-y-4">
      {error ? <ErrorState message={error} /> : null}
      <SectionCard title="Factor Portfolio Summary" subtitle="internally calculated research scores">
        <div className="mb-3 border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
          These are internally calculated research scores inspired by common fundamental and quantitative investment methods. They are not official Morningstar or StarMine ratings.
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric label="Evaluated" value={formatNumber(result.universe_summary?.symbols_scored)} />
          <Metric label="Selected" value={formatNumber(result.universe_summary?.symbols_selected)} />
          <Metric label="Expected Return" value={formatPercent(metrics.expected_annual_return_pct)} />
          <Metric label="Volatility" value={formatPercent(metrics.annual_volatility_pct)} />
          <Metric label="Sharpe" value={formatNumber(metrics.sharpe_ratio)} />
          <Metric label="Objective" value={String(result.optimization_result?.objective || "-")} />
          <Metric label="Avg Score" value={formatNumber(averageScore)} />
          <Metric label="Avg Coverage" value={formatPercent(averageCoverage)} />
        </div>
      </SectionCard>

      <SectionCard title="Stock Ranking" subtitle={`${filteredRows.length} displayed`}>
        <div className="mb-3 grid grid-cols-1 gap-2 lg:grid-cols-4">
          <input className="form-control" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ticker, company, sector" />
          <select className="form-control" value={sectorFilter} onChange={(event) => setSectorFilter(event.target.value)}>
            <option value="">All sectors</option>
            {sectors.map((sector) => <option key={sector} value={sector}>{sector}</option>)}
          </select>
          <label className="flex items-center justify-between border border-line bg-ink px-3 py-2 text-xs">
            Selected only
            <input type="checkbox" checked={selectedOnly} onChange={(event) => setSelectedOnly(event.target.checked)} />
          </label>
          <input className="form-control" type="number" min={0} max={100} value={scoreThreshold} onChange={(event) => setScoreThreshold(Number(event.target.value))} placeholder="Score threshold" />
        </div>
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full min-w-[1120px] border-collapse text-xs">
            <thead className="sticky top-0 bg-panel2 text-left text-[10px] uppercase tracking-[0.14em] text-muted">
              <tr>
                {["Rank", "Ticker", "Company", "Sector", "Quality", "Valuation", "Momentum", "Analyst", "Risk", "Combined", "Coverage", "Status", "Weight"].map((header) => (
                  <th key={header} className="border-b border-line px-3 py-2">{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, index) => (
                <tr key={row.ticker || index} className="cursor-pointer border-b border-line/70 hover:bg-ink" onClick={() => setActiveTicker(row.ticker || null)}>
                  <td className="px-3 py-2">{index + 1}</td>
                  <td className="px-3 py-2 font-mono text-cyan">{row.ticker}</td>
                  <td className="px-3 py-2">{row.company_name || "-"}</td>
                  <td className="px-3 py-2">{row.sector || "-"}</td>
                  <td className="px-3 py-2">{formatNumber(row.fundamental_quality_score)}</td>
                  <td className="px-3 py-2">{formatNumber(row.valuation_score)}</td>
                  <td className="px-3 py-2">{formatNumber(row.momentum_score)}</td>
                  <td className="px-3 py-2">{formatNumber(row.analyst_score)}</td>
                  <td className="px-3 py-2">{formatNumber(row.financial_risk_score)}</td>
                  <td className="px-3 py-2 font-semibold text-text">{formatNumber(row.combined_portfolio_score)}</td>
                  <td className="px-3 py-2">{formatPercent(row.data_coverage_pct)}</td>
                  <td className="px-3 py-2">{row.selection_status || "-"}</td>
                  <td className="px-3 py-2">{formatPercent((row.final_portfolio_weight || 0) * 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <ScoreBarChart rows={rows.slice(0, 20)} />
        <FactorBreakdown row={active} />
      </div>
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <WeightScatter rows={rows} />
        <SectorAllocation rows={rows} />
      </div>

      {result.scenario_analysis?.enabled ? (
        <PortfolioScenarioAnalysis result={factorScenarioPortfolioResult(result)} />
      ) : null}

      {result.warnings?.map((warning) => (
        <div key={warning} className="border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">{warning}</div>
      ))}
    </div>
  );
}

function factorScenarioPortfolioResult(result: FactorPortfolioResult): PortfolioResult {
  return {
    status: "success",
    scenario_analysis: result.scenario_analysis || undefined,
    charts: {
      scenario_analysis: result.scenario_charts || {},
    },
  };
}

function ScoreBarChart({ rows }: { rows: FactorScoreRow[] }) {
  return (
    <SectionCard title="Combined Scores" subtitle="top ranked stocks">
      <Plot
        data={[{
          type: "bar",
          orientation: "h",
          x: rows.map((row) => row.combined_portfolio_score || 0),
          y: rows.map((row) => row.ticker || ""),
          marker: { color: quantTheme.strategy },
        }] as never}
        layout={{ ...plotlyLayoutDefaults, height: 360, xaxis: { ...plotlyLayoutDefaults.xaxis, range: [0, 100] } }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "360px" }}
      />
    </SectionCard>
  );
}

function FactorBreakdown({ row }: { row?: FactorScoreRow }) {
  const values = [
    row?.fundamental_quality_score || 0,
    row?.valuation_score || 0,
    row?.momentum_score || 0,
    row?.analyst_score || 0,
    row?.financial_risk_score || 0,
  ];
  return (
    <SectionCard title="Factor Breakdown" subtitle={row?.ticker || "select a stock"}>
      <Plot
        data={[{
          type: "bar",
          x: ["Quality", "Valuation", "Momentum", "Analyst", "Risk"],
          y: values,
          marker: { color: [quantTheme.positive, quantTheme.benchmark, quantTheme.strategy, quantTheme.warning, quantTheme.neutral] },
        }] as never}
        layout={{ ...plotlyLayoutDefaults, height: 300, yaxis: { ...plotlyLayoutDefaults.yaxis, range: [0, 100] } }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "300px" }}
      />
      <div className="space-y-2 text-xs">
        <Metric label="Selection" value={row?.selection_reason || "-"} />
        <Metric label="Original Return" value={formatPercent((row?.expected_return_original || 0) * 100)} />
        <Metric label="Adjusted Return" value={formatPercent((row?.expected_return_adjusted || 0) * 100)} />
        <div className="border border-line bg-ink px-3 py-2 text-muted">{explain(row)}</div>
      </div>
    </SectionCard>
  );
}

function WeightScatter({ rows }: { rows: FactorScoreRow[] }) {
  return (
    <SectionCard title="Score vs Weight" subtitle="selected portfolio">
      <Plot
        data={[{
          type: "scatter",
          mode: "markers+text",
          x: rows.map((row) => row.combined_portfolio_score || 0),
          y: rows.map((row) => (row.final_portfolio_weight || 0) * 100),
          text: rows.map((row) => row.ticker || ""),
          textposition: "top center",
          marker: { color: quantTheme.positive, size: 9 },
        }] as never}
        layout={{ ...plotlyLayoutDefaults, height: 320, xaxis: { ...plotlyLayoutDefaults.xaxis, title: { text: "Combined score", font: { color: quantTheme.axis, size: 11 } } }, yaxis: { ...plotlyLayoutDefaults.yaxis, title: { text: "Weight %", font: { color: quantTheme.axis, size: 11 } } } }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "320px" }}
      />
    </SectionCard>
  );
}

function SectorAllocation({ rows }: { rows: FactorScoreRow[] }) {
  const allocation = new Map<string, number>();
  rows.forEach((row) => {
    const weight = row.final_portfolio_weight || 0;
    if (weight <= 0) return;
    allocation.set(row.sector || "Unclassified", (allocation.get(row.sector || "Unclassified") || 0) + weight * 100);
  });
  const entries = Array.from(allocation.entries());
  return (
    <SectionCard title="Sector Allocation" subtitle="final selected weights">
      <Plot
        data={[{
          type: "pie",
          labels: entries.map(([sector]) => sector),
          values: entries.map(([, weight]) => weight),
          hole: 0.45,
        }] as never}
        layout={{ ...plotlyLayoutDefaults, height: 320, showlegend: true }}
        config={plotlyConfig}
        className="w-full"
        useResizeHandler
        style={{ width: "100%", height: "320px" }}
      />
    </SectionCard>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border border-line bg-ink px-3 py-2 text-xs">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</span>
      <span className="text-right font-mono text-text">{value}</span>
    </div>
  );
}

function average(values: Array<number | null | undefined>): number | null {
  const usable = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!usable.length) return null;
  return usable.reduce((sum, value) => sum + value, 0) / usable.length;
}

function explain(row?: FactorScoreRow): string {
  if (!row) return "Select a stock to view its deterministic score explanation.";
  const parts = [
    ["quality", row.fundamental_quality_score],
    ["momentum", row.momentum_score],
    ["valuation", row.valuation_score],
    ["risk", row.financial_risk_score],
    ["analyst data", row.analyst_score],
  ].filter(([, value]) => typeof value === "number") as Array<[string, number]>;
  const best = [...parts].sort((a, b) => b[1] - a[1])[0];
  const weakest = [...parts].sort((a, b) => a[1] - b[1])[0];
  if (row.selection_status === "rejected") {
    return `${row.ticker} was excluded because ${String(row.selection_reason || "it did not meet the configured selection rule").toLowerCase()}`;
  }
  return `${row.ticker} ranked with a combined score of ${formatNumber(row.combined_portfolio_score)}. Its strongest area was ${best?.[0] || "available factor data"}, while ${weakest?.[0] || "one factor"} was weaker relative to the evaluated universe.`;
}
