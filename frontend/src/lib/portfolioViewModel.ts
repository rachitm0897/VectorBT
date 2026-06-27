import type { FactorScoreRow, PortfolioResult } from "../api/client";
import { asNumber } from "./numberFormatters";

export const FACTOR_SCORE_ORDER = [
  { key: "fundamental_quality_score", label: "Quality" },
  { key: "valuation_score", label: "Valuation" },
  { key: "momentum_score", label: "Momentum" },
  { key: "analyst_score", label: "Analyst" },
  { key: "financial_risk_score", label: "Risk" },
] as const;

export type RankedFactorScoreRow = FactorScoreRow & {
  rank: number;
  tickerLabel: string;
  chartLabel: string;
  combinedScore: number;
  weightPct: number;
  isSelected: boolean;
  isRejected: boolean;
};

export type WeightRow = {
  symbol: string;
  weightPct: number;
};

export type SectorAllocationRow = {
  sector: string;
  weightPct: number;
};

export function toRankedFactorRows(rows: FactorScoreRow[] = []): RankedFactorScoreRow[] {
  return rows
    .map((row, index) => ({ row, index, score: scoreSortValue(row.combined_portfolio_score) }))
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      const leftTicker = String(left.row.ticker || "");
      const rightTicker = String(right.row.ticker || "");
      return leftTicker.localeCompare(rightTicker) || left.index - right.index;
    })
    .map(({ row }, index) => {
      const rank = index + 1;
      const ticker = String(row.ticker || "Unknown");
      const status = String(row.selection_status || "").toLowerCase();
      const combinedScore = asNumber(row.combined_portfolio_score) ?? 0;
      const weight = asNumber(row.final_portfolio_weight) ?? 0;
      return {
        ...row,
        rank,
        tickerLabel: `${rank}. ${ticker}`,
        chartLabel: `${rank}. ${ticker}`,
        combinedScore,
        weightPct: valuesLookLikePercent(weight) ? weight : weight * 100,
        isSelected: status === "selected",
        isRejected: status === "rejected",
      };
    });
}

export function toFactorWeightRows(rows: RankedFactorScoreRow[] = []): WeightRow[] {
  return rows
    .filter((row) => row.weightPct > 0)
    .map((row) => ({ symbol: String(row.ticker || "Unknown"), weightPct: row.weightPct }))
    .sort((left, right) => right.weightPct - left.weightPct);
}

export function toSectorAllocationRows(rows: RankedFactorScoreRow[] = []): SectorAllocationRow[] {
  const allocation = new Map<string, number>();
  rows.forEach((row) => {
    if (row.weightPct <= 0) return;
    const sector = String(row.sector || "Unclassified");
    allocation.set(sector, (allocation.get(sector) || 0) + row.weightPct);
  });
  return Array.from(allocation.entries())
    .map(([sector, weightPct]) => ({ sector, weightPct }))
    .sort((left, right) => right.weightPct - left.weightPct);
}

export function toPortfolioWeightRows(result: PortfolioResult): WeightRow[] {
  const objectiveWeights =
    result.objective === "min_volatility"
      ? result.charts?.min_volatility_portfolio?.weights
      : result.charts?.max_sharpe_portfolio?.weights;
  const rawWeights = hasWeights(result.weights) ? result.weights : objectiveWeights || {};
  const parsedRows = Object.entries(rawWeights)
    .map(([symbol, weight]) => ({ symbol, weight: asNumber(weight) }))
    .filter((row): row is { symbol: string; weight: number } => Boolean(row.symbol) && row.weight !== null);

  const decimals = parsedRows.length > 0 && parsedRows.every((row) => Math.abs(row.weight) <= 1);
  return parsedRows
    .map((row) => ({
      symbol: row.symbol,
      weightPct: decimals ? row.weight * 100 : row.weight,
    }))
    .sort((left, right) => right.weightPct - left.weightPct);
}

export function totalWeightPct(rows: WeightRow[] | SectorAllocationRow[]): number {
  return rows.reduce((sum, row) => sum + row.weightPct, 0);
}

export function weightTotalIsApprox100(totalPct: number, tolerancePct = 0.75): boolean {
  return Math.abs(totalPct - 100) <= tolerancePct;
}

export function selectedFactorRows(rows: RankedFactorScoreRow[]): RankedFactorScoreRow[] {
  return rows.filter((row) => row.isSelected || row.weightPct > 0);
}

function scoreSortValue(value: unknown): number {
  return asNumber(value) ?? Number.NEGATIVE_INFINITY;
}

function valuesLookLikePercent(value: number): boolean {
  return Math.abs(value) > 1;
}

function hasWeights(weights: PortfolioResult["weights"]): weights is Record<string, number> {
  return Boolean(weights && Object.keys(weights).length);
}
