import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import ts from "typescript";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const helpers = loadPortfolioViewModel();

test("combined score rows sort descending with stable ranks", () => {
  const rows = helpers.toRankedFactorRows([
    { ticker: "LOW", combined_portfolio_score: 41.21, final_portfolio_weight: 0, selection_status: "rejected" },
    { ticker: "HIGH", combined_portfolio_score: 82.43, final_portfolio_weight: 0.35, selection_status: "selected" },
    { ticker: "MID", combined_portfolio_score: 76.8, final_portfolio_weight: 0.25, selection_status: "selected" },
  ]);

  assert.deepEqual(rows.map((row) => row.ticker), ["HIGH", "MID", "LOW"]);
  assert.deepEqual(rows.map((row) => row.rank), [1, 2, 3]);
  assert.equal(rows[0].chartLabel, "1. HIGH");
  assert.equal(rows[0].weightPct, 35);
  assert.equal(rows[2].isRejected, true);
});

test("portfolio weights sort highest to lowest and keep percent totals explicit", () => {
  const rows = helpers.toPortfolioWeightRows({
    objective: "max_sharpe",
    weights: { AAPL: 0.25, MSFT: 0.5, NVDA: 0.25 },
  });

  assertJsonEqual(rows.map((row) => row.symbol), ["MSFT", "AAPL", "NVDA"]);
  assert.equal(helpers.totalWeightPct(rows), 100);
  assert.equal(helpers.weightTotalIsApprox100(helpers.totalWeightPct(rows)), true);
});

test("sector allocation aggregates selected holding weights in descending order", () => {
  const ranked = helpers.toRankedFactorRows([
    { ticker: "A", sector: "Technology", combined_portfolio_score: 90, final_portfolio_weight: 0.2, selection_status: "selected" },
    { ticker: "B", sector: "Healthcare", combined_portfolio_score: 80, final_portfolio_weight: 0.5, selection_status: "selected" },
    { ticker: "C", sector: "Technology", combined_portfolio_score: 70, final_portfolio_weight: 0.3, selection_status: "selected" },
  ]);

  const sectors = helpers.toSectorAllocationRows(ranked);

  assertJsonEqual(sectors, [
    { sector: "Technology", weightPct: 50 },
    { sector: "Healthcare", weightPct: 50 },
  ]);
});

test("portfolio charts keep required score and scenario safeguards in source", () => {
  const factorDashboard = readFileSync(resolve(root, "src/components/portfolio/FactorPortfolioResultDashboard.tsx"), "utf8");
  const weightsChart = readFileSync(resolve(root, "src/components/portfolio/PortfolioWeightsChart.tsx"), "utf8");
  const scenarioChart = readFileSync(resolve(root, "src/components/portfolio/PortfolioScenarioAnalysis.tsx"), "utf8");

  assert.match(factorDashboard, /rows\.slice\(0,\s*10\)/);
  assert.match(factorDashboard, /range:\s*\[0,\s*100\]/);
  assert.match(factorDashboard, /autorange:\s*"reversed"/);
  assert.match(weightsChart, /toPortfolioWeightRows/);
  assert.match(weightsChart, /autorange:\s*"reversed"/);
  assert.match(scenarioChart, /const \[showSamples, setShowSamples\] = useState\(false\)/);
  assert.match(scenarioChart, /showSamples \?/);
});

function loadPortfolioViewModel() {
  const source = readFileSync(resolve(root, "src/lib/portfolioViewModel.ts"), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2021,
      esModuleInterop: true,
    },
  }).outputText;
  const module = { exports: {} };
  const sandbox = {
    module,
    exports: module.exports,
    require: (id) => {
      if (id === "./numberFormatters") return { asNumber };
      throw new Error(`Unexpected import: ${id}`);
    },
  };
  vm.runInNewContext(output, sandbox, { filename: "portfolioViewModel.js" });
  return module.exports;
}

function asNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function assertJsonEqual(actual, expected) {
  assert.equal(JSON.stringify(actual), JSON.stringify(expected));
}
