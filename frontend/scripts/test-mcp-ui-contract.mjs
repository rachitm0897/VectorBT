import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const read = (path) => readFileSync(join(root, path), "utf8");

describe("MCP-first UI contract", () => {
  it("renders exactly four primary full-window tabs", () => {
    const tabs = read("src/app/tabs.ts");
    const labels = [...tabs.matchAll(/label: "([^"]+)"/g)].map((match) => match[1]);
    assert.deepEqual(labels, [
      "AI Research Chat",
      "Manual Research Lab",
      "Strategy Discovery Lab",
      "System / Health / Settings",
    ]);
  });

  it("does not compose the old collapsed sidebar shell", () => {
    const app = read("src/app/App.tsx");
    assert.equal(app.includes("CollapsiblePanel"), false);
    assert.equal(app.includes("Sidebar"), false);
    assert.equal(app.includes("AppShell"), false);
  });

  it("strategy table exposes imported and non-executable statuses", () => {
    const table = read("src/features/strategies/StrategyRegistryTable.tsx");
    assert.match(table, /source_type/);
    assert.match(table, /imported/);
    assert.match(table, /catalogue_only/);
    assert.match(table, /missing_data/);
    assert.match(table, /incomplete_rules/);
    assert.match(table, /Disabled/);
  });

  it("manual lab exposes sector flow, optimizer parameters, and editable Monte Carlo settings", () => {
    const lab = read("src/features/manual-lab/ManualResearchLab.tsx");
    for (const needle of [
      "A. Strategy Backtest",
      "B. Sector-Wise Stock Collection",
      "C. Portfolio Optimizer",
      "D. Monte Carlo",
      "Raw Asset Markowitz",
      "Strategy-Conditioned Markowitz",
      "gross_exposure_limit",
      "net_exposure",
      "target_return",
      "block_bootstrap",
      "Resolve Sector Symbols Through MCP",
    ]) {
      assert.match(lab, new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    }
  });

  it("discovery tab shows processing-not-configured failures clearly", () => {
    const discovery = read("src/features/discovery/StrategyDiscoveryLab.tsx");
    assert.match(discovery, /approved_processing_not_configured/);
    assert.match(discovery, /No backtest, classification, or promotion was performed/);
  });

  it("system tab centralizes API keys, health, tools, diagnostics, and admin actions", () => {
    const system = read("src/features/system/SystemSettings.tsx");
    for (const needle of [
      "A. API Keys",
      "ApiKeyPanel",
      "B. System Health",
      "C. MCP Tools",
      "D. Diagnostics",
      "E. Admin Actions",
      "Sync Strategy Registry",
      "Clear Local UI State",
    ]) {
      assert.match(system, new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    }
  });
});
