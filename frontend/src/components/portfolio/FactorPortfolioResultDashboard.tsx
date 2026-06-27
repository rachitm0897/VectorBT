import { useMemo, useState } from "react";
import Plot from "react-plotly.js";
import type { FactorPortfolioResult, PortfolioResult } from "../../api/client";
import { formatNumber, formatPercent, formatScore } from "../../lib/numberFormatters";
import {
  FACTOR_SCORE_ORDER,
  selectedFactorRows,
  toRankedFactorRows,
  toSectorAllocationRows,
  totalWeightPct,
  weightTotalIsApprox100,
  type RankedFactorScoreRow,
} from "../../lib/portfolioViewModel";
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

type SortKey =
  | "rank"
  | "ticker"
  | "company"
  | "sector"
  | "quality"
  | "valuation"
  | "momentum"
  | "analyst"
  | "risk"
  | "combined"
  | "coverage"
  | "status"
  | "weight";

type SortDirection = "asc" | "desc";

const rankingColumns: Array<{ key: SortKey; label: string }> = [
  { key: "rank", label: "Rank" },
  { key: "ticker", label: "Ticker" },
  { key: "company", label: "Company" },
  { key: "sector", label: "Sector" },
  { key: "quality", label: "Quality" },
  { key: "valuation", label: "Valuation" },
  { key: "momentum", label: "Momentum" },
  { key: "analyst", label: "Analyst" },
  { key: "risk", label: "Risk" },
  { key: "combined", label: "Combined" },
  { key: "coverage", label: "Coverage" },
  { key: "status", label: "Status" },
  { key: "weight", label: "Weight" },
];

export default function FactorPortfolioResultDashboard({ result, isLoading, error }: FactorPortfolioResultDashboardProps) {
  const [search, setSearch] = useState("");
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [sectorFilter, setSectorFilter] = useState("");
  const [scoreThreshold, setScoreThreshold] = useState(0);
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const rows = useMemo(() => toRankedFactorRows(result?.factor_scores || []), [result?.factor_scores]);
  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      const query = search.trim().toUpperCase();
      if (query && ![row.ticker, row.company_name, row.sector].join(" ").toUpperCase().includes(query)) return false;
      if (selectedOnly && !row.isSelected) return false;
      if (sectorFilter && row.sector !== sectorFilter) return false;
      if (row.combinedScore < scoreThreshold) return false;
      return true;
    });
  }, [rows, scoreThreshold, search, sectorFilter, selectedOnly]);
  const displayedRows = useMemo(
    () => sortFactorRows(filteredRows, sortKey, sortDirection),
    [filteredRows, sortDirection, sortKey],
  );
  const sectors = useMemo(
    () => Array.from(new Set(rows.map((row) => row.sector).filter(Boolean))).sort() as string[],
    [rows],
  );
  const active = rows.find((row) => row.ticker === activeTicker) || rows[0];

  if (isLoading) return <LoadingState label="Constructing factor portfolio" />;
  if (error && !result) return <ErrorState message={error} />;
  if (!result) {
    return <EmptyState title="No factor portfolio loaded" message="Configure a factor model, select a universe, and construct a portfolio." />;
  }

  const selectedRows = selectedFactorRows(rows);
  const metrics = result.optimization_result?.metrics || {};
  const averageScore = average(selectedRows.map((item) => item.combinedScore));
  const averageCoverage = average(selectedRows.map((item) => item.data_coverage_pct));

  function updateSort(nextKey: SortKey) {
    if (nextKey === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "rank" || nextKey === "ticker" || nextKey === "company" ? "asc" : "desc");
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorState message={error} /> : null}
      <SectionCard title="Factor Portfolio Summary" subtitle="internally calculated research scores">
        <div className="mb-3 border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
          These are internally calculated research scores inspired by common fundamental and quantitative investment methods. They are not official Morningstar or StarMine ratings.
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric label="Evaluated" value={formatNumber(result.universe_summary?.symbols_scored, 0)} />
          <Metric label="Selected" value={formatNumber(result.universe_summary?.symbols_selected, 0)} />
          <Metric label="Expected Return" value={formatPercent(metrics.expected_annual_return_pct, 1)} />
          <Metric label="Volatility" value={formatPercent(metrics.annual_volatility_pct, 1)} />
          <Metric label="Sharpe" value={formatNumber(metrics.sharpe_ratio, 2)} />
          <Metric label="Avg Score" value={formatScore(averageScore)} />
          <Metric label="Avg Coverage" value={formatPercent(averageCoverage, 1)} />
        </div>
      </SectionCard>

      <SectionCard title="Stock Ranking" subtitle={`${displayedRows.length} displayed, ranked by combined score`}>
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
                {rankingColumns.map((column) => (
                  <th key={column.key} className="border-b border-line px-3 py-2">
                    <button className="flex items-center gap-1 uppercase" type="button" onClick={() => updateSort(column.key)}>
                      {column.label}
                      {sortKey === column.key ? <span>{sortDirection === "asc" ? "^" : "v"}</span> : null}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayedRows.map((row, index) => (
                <tr
                  key={row.ticker || index}
                  className={`cursor-pointer border-b border-line/70 hover:bg-ink ${row.isSelected ? "bg-cyan/5" : row.isRejected ? "text-muted" : ""}`}
                  onClick={() => setActiveTicker(row.ticker || null)}
                >
                  <td className="px-3 py-2">{row.rank}</td>
                  <td className="sticky left-0 bg-panel px-3 py-2 font-mono text-cyan">{row.ticker}</td>
                  <td className="px-3 py-2">{row.company_name || "-"}</td>
                  <td className="px-3 py-2">{row.sector || "-"}</td>
                  <td className="px-3 py-2">{formatScore(row.fundamental_quality_score)}</td>
                  <td className="px-3 py-2">{formatScore(row.valuation_score)}</td>
                  <td className="px-3 py-2">{formatScore(row.momentum_score)}</td>
                  <td className="px-3 py-2">{formatScore(row.analyst_score)}</td>
                  <td className="px-3 py-2">{formatScore(row.financial_risk_score)}</td>
                  <td className="px-3 py-2 font-semibold text-text">{formatScore(row.combined_portfolio_score)}</td>
                  <td className="px-3 py-2">{formatPercent(row.data_coverage_pct, 1)}</td>
                  <td className={row.isSelected ? "px-3 py-2 font-semibold text-cyan" : "px-3 py-2"}>{row.selection_status || "-"}</td>
                  <td className="px-3 py-2">{formatPercent(row.weightPct, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <ScoreBarChart rows={rows} />
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

function ScoreBarChart({ rows }: { rows: RankedFactorScoreRow[] }) {
  const [showAll, setShowAll] = useState(false);
  const visibleRows = showAll ? rows : rows.slice(0, 10);
  const plotHeight = Math.max(320, visibleRows.length * 34 + 112);

  return (
    <SectionCard
      title="Combined Stock Score"
      subtitle="0-100 scale, higher is better"
      action={
        rows.length > 10 ? (
          <button
            className="border border-line px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted transition hover:border-cyan hover:text-cyan"
            type="button"
            onClick={() => setShowAll((current) => !current)}
          >
            {showAll ? "Top 10" : "Show All"}
          </button>
        ) : null
      }
    >
      {visibleRows.length ? (
        <div className="max-h-[560px] overflow-y-auto overflow-x-hidden">
          <Plot
            data={[{
              type: "bar",
              orientation: "h",
              x: visibleRows.map((row) => row.combinedScore),
              y: visibleRows.map((row) => row.chartLabel),
              text: visibleRows.map((row) => formatScore(row.combinedScore)),
              textposition: "auto",
              marker: {
                color: visibleRows.map((row) => {
                  if (row.isSelected) return quantTheme.strategy;
                  if (row.isRejected) return "rgba(139,153,173,0.32)";
                  return quantTheme.benchmark;
                }),
                line: {
                  color: visibleRows.map((row) => (row.isSelected ? quantTheme.text : "rgba(230,237,247,0.16)")),
                  width: visibleRows.map((row) => (row.isSelected ? 1.5 : 1)),
                },
              },
              customdata: visibleRows.map((row) => [
                row.ticker || "-",
                row.company_name || "-",
                row.rank,
                formatScore(row.combined_portfolio_score),
                formatScore(row.fundamental_quality_score),
                formatScore(row.valuation_score),
                formatScore(row.momentum_score),
                formatScore(row.analyst_score),
                formatScore(row.financial_risk_score),
                row.selection_status || "-",
              ]),
              hovertemplate:
                "Ticker %{customdata[0]}<br>Company %{customdata[1]}<br>Rank %{customdata[2]}<br>Combined score %{customdata[3]}<br>Quality %{customdata[4]}<br>Valuation %{customdata[5]}<br>Momentum %{customdata[6]}<br>Analyst %{customdata[7]}<br>Risk %{customdata[8]}<br>Status %{customdata[9]}<extra></extra>",
            }] as never}
            layout={{
              ...plotlyLayoutDefaults,
              height: plotHeight,
              margin: { l: 104, r: 36, t: 18, b: 54 },
              xaxis: {
                ...plotlyLayoutDefaults.xaxis,
                range: [0, 100],
                title: { text: "Combined Score (0-100, higher is better)", font: { color: quantTheme.axis, size: 11 } },
                zeroline: false,
              },
              yaxis: {
                ...plotlyLayoutDefaults.yaxis,
                categoryorder: "array",
                categoryarray: visibleRows.map((row) => row.chartLabel),
                autorange: "reversed",
                automargin: true,
              },
              showlegend: false,
            }}
            config={plotlyConfig}
            className="w-full"
            useResizeHandler
            style={{ width: "100%", height: `${plotHeight}px` }}
          />
        </div>
      ) : (
        <EmptyState title="No factor scores" message="The factor result did not include stock scores." />
      )}
    </SectionCard>
  );
}

function FactorBreakdown({ row }: { row?: RankedFactorScoreRow }) {
  const values = FACTOR_SCORE_ORDER.map((factor) => ({
    ...factor,
    value: row ? Number(row[factor.key] || 0) : 0,
  }));
  return (
    <SectionCard title="Single Stock Factor Breakdown" subtitle={row ? `${row.rank}. ${row.ticker}` : "select a stock"}>
      {row ? (
        <>
          <Plot
            data={[{
              type: "bar",
              orientation: "h",
              x: values.map((item) => item.value),
              y: values.map((item) => item.label),
              text: values.map((item) => formatScore(item.value)),
              textposition: "auto",
              marker: { color: quantTheme.strategy },
              hovertemplate: "%{y}<br>Score %{x:.1f}<extra></extra>",
            }] as never}
            layout={{
              ...plotlyLayoutDefaults,
              height: 270,
              margin: { l: 78, r: 24, t: 12, b: 42 },
              xaxis: { ...plotlyLayoutDefaults.xaxis, range: [0, 100], title: { text: "Score (0-100)", font: { color: quantTheme.axis, size: 11 } } },
              yaxis: { ...plotlyLayoutDefaults.yaxis, autorange: "reversed" },
              showlegend: false,
            }}
            config={plotlyConfig}
            className="w-full"
            useResizeHandler
            style={{ width: "100%", height: "270px" }}
          />
          <div className="space-y-2 text-xs">
            {values.map((item) => <Metric key={item.key} label={item.label} value={formatScore(item.value)} />)}
            <Metric label="Combined" value={formatScore(row.combined_portfolio_score)} />
            <Metric label="Selection" value={row.selection_status || "-"} />
            <Metric label="Original Return" value={formatReturnDecimal(row.expected_return_original)} />
            <Metric label="Adjusted Return" value={formatReturnDecimal(row.expected_return_adjusted)} />
            <div className="border border-line bg-ink px-3 py-2 text-muted">{explain(row)}</div>
          </div>
        </>
      ) : (
        <EmptyState title="No stock selected" message="Select a row to view factor details." />
      )}
    </SectionCard>
  );
}

function WeightScatter({ rows }: { rows: RankedFactorScoreRow[] }) {
  const selectedRows = selectedFactorRows(rows);
  return (
    <SectionCard title="Score vs Portfolio Weight" subtitle="factor rank compared with Markowitz allocation">
      {selectedRows.length ? (
        <>
          <Plot
            data={[{
              type: "scatter",
              mode: "markers",
              x: selectedRows.map((row) => row.combinedScore),
              y: selectedRows.map((row) => row.weightPct),
              marker: {
                color: selectedRows.map((row) => (row.isSelected ? quantTheme.strategy : quantTheme.neutral)),
                size: 10,
                line: { color: quantTheme.text, width: 1 },
              },
              customdata: selectedRows.map((row) => [
                row.ticker || "-",
                row.rank,
                formatScore(row.combinedScore),
                formatPercent(row.weightPct, 1),
              ]),
              hovertemplate: "Ticker %{customdata[0]}<br>Rank %{customdata[1]}<br>Combined score %{customdata[2]}<br>Portfolio weight %{customdata[3]}<extra></extra>",
            }] as never}
            layout={{
              ...plotlyLayoutDefaults,
              height: 320,
              xaxis: {
                ...plotlyLayoutDefaults.xaxis,
                range: [0, 100],
                title: { text: "Combined Score", font: { color: quantTheme.axis, size: 11 } },
              },
              yaxis: {
                ...plotlyLayoutDefaults.yaxis,
                title: { text: "Portfolio Weight (%)", font: { color: quantTheme.axis, size: 11 } },
                rangemode: "tozero",
                ticksuffix: "%",
              },
              showlegend: false,
            }}
            config={plotlyConfig}
            className="w-full"
            useResizeHandler
            style={{ width: "100%", height: "320px" }}
          />
          <div className="border border-line bg-ink px-3 py-2 text-xs leading-5 text-muted">
            Higher factor scores do not automatically produce higher weights because Markowitz allocation also reflects covariance, volatility, and the configured constraints.
          </div>
        </>
      ) : (
        <EmptyState title="No selected weights" message="Selected holdings did not include portfolio weights." />
      )}
    </SectionCard>
  );
}

function SectorAllocation({ rows }: { rows: RankedFactorScoreRow[] }) {
  const entries = toSectorAllocationRows(rows);
  const total = totalWeightPct(entries);
  const height = Math.max(280, entries.length * 34 + 112);
  return (
    <SectionCard title="Sector Allocation" subtitle="final selected weights">
      {entries.length ? (
        <>
          {!weightTotalIsApprox100(total) ? (
            <div className="mb-3 border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
              Sector weights total {formatPercent(total, 1)}; expected approximately 100%.
            </div>
          ) : null}
          <Plot
            data={[{
              type: "bar",
              orientation: "h",
              x: entries.map((entry) => entry.weightPct),
              y: entries.map((entry) => entry.sector),
              text: entries.map((entry) => formatPercent(entry.weightPct, 1)),
              textposition: "auto",
              marker: { color: quantTheme.benchmark, line: { color: "rgba(230,237,247,0.18)", width: 1 } },
              hovertemplate: "Sector %{y}<br>Allocation %{x:.1f}%<extra></extra>",
            }] as never}
            layout={{
              ...plotlyLayoutDefaults,
              height,
              margin: { l: 112, r: 34, t: 12, b: 48 },
              xaxis: { ...plotlyLayoutDefaults.xaxis, title: { text: "Allocation (%)", font: { color: quantTheme.axis, size: 11 } }, rangemode: "tozero", ticksuffix: "%" },
              yaxis: { ...plotlyLayoutDefaults.yaxis, categoryorder: "array", categoryarray: entries.map((entry) => entry.sector), autorange: "reversed", automargin: true },
              showlegend: false,
            }}
            config={plotlyConfig}
            className="w-full"
            useResizeHandler
            style={{ width: "100%", height: `${height}px` }}
          />
        </>
      ) : (
        <EmptyState title="No sector weights" message="The selected holdings did not include sector allocations." />
      )}
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

function explain(row?: RankedFactorScoreRow): string {
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
  return `${row.ticker} ranked ${row.rank} with a combined score of ${formatScore(row.combined_portfolio_score)}. Its strongest area was ${best?.[0] || "available factor data"}, while ${weakest?.[0] || "one factor"} was weaker relative to the evaluated universe.`;
}

function formatReturnDecimal(value: unknown): string {
  const parsed = typeof value === "number" && Number.isFinite(value) ? value : null;
  return parsed === null ? "-" : formatPercent(parsed * 100, 1);
}

function sortFactorRows(rows: RankedFactorScoreRow[], key: SortKey, direction: SortDirection): RankedFactorScoreRow[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const leftValue = sortValue(left, key);
    const rightValue = sortValue(right, key);
    if (typeof leftValue === "number" && typeof rightValue === "number") {
      return (leftValue - rightValue || left.rank - right.rank) * multiplier;
    }
    return (String(leftValue).localeCompare(String(rightValue)) || left.rank - right.rank) * multiplier;
  });
}

function sortValue(row: RankedFactorScoreRow, key: SortKey): string | number {
  if (key === "rank") return row.rank;
  if (key === "ticker") return String(row.ticker || "");
  if (key === "company") return String(row.company_name || "");
  if (key === "sector") return String(row.sector || "");
  if (key === "quality") return numberSortValue(row.fundamental_quality_score);
  if (key === "valuation") return numberSortValue(row.valuation_score);
  if (key === "momentum") return numberSortValue(row.momentum_score);
  if (key === "analyst") return numberSortValue(row.analyst_score);
  if (key === "risk") return numberSortValue(row.financial_risk_score);
  if (key === "combined") return row.combinedScore;
  if (key === "coverage") return numberSortValue(row.data_coverage_pct);
  if (key === "weight") return row.weightPct;
  return String(row.selection_status || "");
}

function numberSortValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}
