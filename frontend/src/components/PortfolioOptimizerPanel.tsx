import { useEffect, useMemo, useState } from "react";
import {
  fetchSectors,
  fetchStocksBySector,
  type PortfolioMonteCarloConfig,
  type PortfolioOptimizationRequest,
  type PortfolioScenarioName,
  type PortfolioScenarioOverride,
  type StockUniverseItem,
} from "../api/client";

type PortfolioOptimizerPanelProps = {
  isLoading: boolean;
  onSubmit: (payload: PortfolioOptimizationRequest) => void;
};

type SelectionMode = "all" | "sector";

const lookbacks: PortfolioOptimizationRequest["lookback"][] = ["1mo", "6mo", "1y", "2y", "5y"];
const objectives: PortfolioOptimizationRequest["objective"][] = ["max_sharpe", "min_volatility"];
const maxPrototypeSymbols = 20;
const scenarioOptions: Array<{ name: PortfolioScenarioName; label: string }> = [
  { name: "neutral", label: "Neutral" },
  { name: "bullish", label: "Bullish" },
  { name: "bearish", label: "Bearish" },
  { name: "crash", label: "Crash" },
];
const overrideFields: Array<{
  key: keyof PortfolioScenarioOverride;
  label: string;
  min: number;
  max: number;
  step: number;
}> = [
  { key: "drift_shift_annual", label: "Annual Drift Shift", min: -0.5, max: 0.5, step: 0.01 },
  { key: "volatility_multiplier", label: "Volatility Multiplier", min: 0.25, max: 4, step: 0.05 },
  { key: "initial_shock_pct", label: "Initial Shock", min: -0.8, max: 0.8, step: 0.01 },
];

type ScenarioOverrideInputs = Record<PortfolioScenarioName, Record<keyof PortfolioScenarioOverride, string>>;

export default function PortfolioOptimizerPanel({ isLoading, onSubmit }: PortfolioOptimizerPanelProps) {
  const [selectionMode, setSelectionMode] = useState<SelectionMode>("all");
  const [sectors, setSectors] = useState<string[]>([]);
  const [sector, setSector] = useState("");
  const [stocks, setStocks] = useState<StockUniverseItem[]>([]);
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const [manualSymbolsText, setManualSymbolsText] = useState("AAPL MSFT NVDA GOOGL");
  const [searchText, setSearchText] = useState("");
  const [lookback, setLookback] = useState<PortfolioOptimizationRequest["lookback"]>("2y");
  const [objective, setObjective] = useState<PortfolioOptimizationRequest["objective"]>("max_sharpe");
  const [riskFreeRate, setRiskFreeRate] = useState(0);
  const [maxWeight, setMaxWeight] = useState(0.6);
  const [allowShort, setAllowShort] = useState(false);
  const [frontierPoints, setFrontierPoints] = useState(3000);
  const [scenarioEnabled, setScenarioEnabled] = useState(false);
  const [selectedScenarios, setSelectedScenarios] = useState<PortfolioScenarioName[]>(
    scenarioOptions.map((item) => item.name),
  );
  const [scenarioDays, setScenarioDays] = useState(60);
  const [scenarioSimulations, setScenarioSimulations] = useState(500);
  const [scenarioBlockSize, setScenarioBlockSize] = useState(5);
  const [scenarioOverrides, setScenarioOverrides] = useState<ScenarioOverrideInputs>(
    createEmptyScenarioOverrides(),
  );
  const [universeError, setUniverseError] = useState<string | null>(null);
  const [selectionWarning, setSelectionWarning] = useState<string | null>(null);
  const [isUniverseLoading, setIsUniverseLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setIsUniverseLoading(true);
    setUniverseError(null);
    fetchSectors()
      .then((items) => {
        if (cancelled) return;
        setSectors(items);
        setSector((current) => current || items[0] || "");
      })
      .catch((error) => {
        if (!cancelled) setUniverseError(error instanceof Error ? error.message : "Universe sectors failed.");
      })
      .finally(() => {
        if (!cancelled) setIsUniverseLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const requestedSector = selectionMode === "sector" ? sector : undefined;
    if (selectionMode === "sector" && !requestedSector) {
      setStocks([]);
      return;
    }

    setIsUniverseLoading(true);
    setUniverseError(null);
    fetchStocksBySector(requestedSector)
      .then((items) => {
        if (cancelled) return;
        setStocks(items);
      })
      .catch((error) => {
        if (!cancelled) setUniverseError(error instanceof Error ? error.message : "Universe stocks failed.");
      })
      .finally(() => {
        if (!cancelled) setIsUniverseLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectionMode, sector]);

  const manualSymbols = useMemo(() => parseSymbols(manualSymbolsText), [manualSymbolsText]);
  const payloadSymbols = useMemo(
    () => uniqueSymbols([...selectedSymbols, ...manualSymbols]),
    [manualSymbols, selectedSymbols],
  );
  const filteredStocks = useMemo(() => filterStocks(stocks, searchText), [searchText, stocks]);
  const isSectorRequest = selectionMode === "sector" && Boolean(sector);
  const tooManySymbols = !isSectorRequest && payloadSymbols.length > maxPrototypeSymbols;
  const canRun =
    (isSectorRequest || (payloadSymbols.length >= 2 && payloadSymbols.length <= maxPrototypeSymbols)) &&
    !isLoading;
  const visibleLabel = selectionMode === "sector" && sector ? `${sector} stocks` : "all stocks";
  const warning =
    selectionWarning ||
    (tooManySymbols ? `Prototype optimizer supports up to ${maxPrototypeSymbols} stocks. Remove ${payloadSymbols.length - maxPrototypeSymbols} symbol(s).` : null);

  function submit() {
    if (tooManySymbols) {
      setSelectionWarning(`Prototype optimizer supports up to ${maxPrototypeSymbols} stocks.`);
      return;
    }
    const scenarioConfig = buildScenarioConfig(
      scenarioEnabled,
      selectedScenarios,
      scenarioDays,
      scenarioSimulations,
      scenarioBlockSize,
      scenarioOverrides,
    );
    onSubmit({
      symbols: isSectorRequest ? [] : payloadSymbols,
      sector: isSectorRequest ? sector : undefined,
      lookback,
      resolution: "D",
      objective,
      risk_free_rate: clampNumber(riskFreeRate, 0, 0.25, 0),
      allow_short: allowShort,
      max_weight: clampNumber(maxWeight, 0.05, 1, 0.6),
      num_frontier_portfolios: Math.round(clampNumber(frontierPoints, 100, 10000, 3000)),
      monte_carlo: scenarioConfig,
    });
  }

  function toggleSymbol(symbol: string) {
    setSelectedSymbols((current) => {
      if (current.includes(symbol)) {
        setSelectionWarning(null);
        return current.filter((item) => item !== symbol);
      }

      const nextPayload = uniqueSymbols([...current, symbol, ...manualSymbols]);
      if (nextPayload.length > maxPrototypeSymbols) {
        setSelectionWarning(`Only ${maxPrototypeSymbols} stocks can be selected for this prototype.`);
        return current;
      }

      setSelectionWarning(null);
      return uniqueSymbols([...current, symbol]);
    });
  }

  function selectAllVisible() {
    let capped = false;
    const next = [...selectedSymbols];
    for (const stock of filteredStocks) {
      const ticker = stock.ticker;
      if (!ticker || next.includes(ticker) || manualSymbols.includes(ticker)) continue;
      if (uniqueSymbols([...next, ticker, ...manualSymbols]).length > maxPrototypeSymbols) {
        capped = true;
        break;
      }
      next.push(ticker);
    }
    setSelectedSymbols(uniqueSymbols(next));
    setSelectionWarning(
      capped ? `Only the first ${maxPrototypeSymbols} visible stocks were selected for this prototype.` : null,
    );
  }

  function clearSelection() {
    setSelectedSymbols([]);
    setManualSymbolsText("");
    setSelectionWarning(null);
  }

  function removeSymbol(symbol: string) {
    setSelectedSymbols((current) => current.filter((item) => item !== symbol));
    setManualSymbolsText((current) =>
      parseSymbols(current)
        .filter((item) => item !== symbol)
        .join(" "),
    );
    setSelectionWarning(null);
  }

  function toggleScenarioEnabled(enabled: boolean) {
    setScenarioEnabled(enabled);
    if (enabled && selectedScenarios.length === 0) {
      setSelectedScenarios(scenarioOptions.map((item) => item.name));
    }
  }

  function toggleScenario(name: PortfolioScenarioName) {
    setSelectedScenarios((current) => {
      if (current.includes(name)) {
        if (current.length === 1) return current;
        return current.filter((item) => item !== name);
      }
      return scenarioOptions
        .map((item) => item.name)
        .filter((item) => item === name || current.includes(item));
    });
  }

  function updateScenarioOverride(
    scenario: PortfolioScenarioName,
    field: keyof PortfolioScenarioOverride,
    value: string,
  ) {
    setScenarioOverrides((current) => ({
      ...current,
      [scenario]: {
        ...current[scenario],
        [field]: value,
      },
    }));
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="space-y-2">
        <span className="form-label">Selection Mode</span>
        <div className="grid grid-cols-2 border border-line bg-ink p-1">
          <button
            className={modeButtonClass(selectionMode === "all")}
            type="button"
            onClick={() => setSelectionMode("all")}
          >
            All Stocks
          </button>
          <button
            className={modeButtonClass(selectionMode === "sector")}
            type="button"
            onClick={() => setSelectionMode("sector")}
          >
            By Sector
          </button>
        </div>
      </div>

      {selectionMode === "sector" ? (
        <label className="space-y-2">
          <span className="form-label">Sector</span>
          <select className="form-control" value={sector} onChange={(event) => setSector(event.target.value)}>
            {sectors.length ? null : <option value="">Loading sectors</option>}
            {sectors.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {selectionMode === "all" ? (
        <>
          <label className="space-y-2">
            <span className="form-label">Search Universe</span>
            <input
              className="form-control"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="Filter by ticker, company, or sector"
              spellCheck={false}
            />
          </label>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="form-label">
                Stocks <span className="text-muted">({filteredStocks.length} visible, {visibleLabel})</span>
              </span>
              <div className="flex gap-2">
                <button
                  className="border border-cyan/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan transition hover:bg-cyan/10 disabled:cursor-not-allowed disabled:border-line disabled:text-muted"
                  type="button"
                  disabled={!filteredStocks.length}
                  onClick={selectAllVisible}
                >
                  Select All Visible
                </button>
                <button
                  className="border border-line px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted transition hover:border-red hover:text-red"
                  type="button"
                  onClick={clearSelection}
                >
                  Clear Selection
                </button>
              </div>
            </div>

            <div className="max-h-48 overflow-auto border border-line bg-ink">
              {isUniverseLoading ? (
                <div className="px-3 py-6 text-center text-xs uppercase tracking-[0.14em] text-muted">Loading Universe</div>
              ) : null}
              {!isUniverseLoading && !filteredStocks.length ? (
                <div className="px-3 py-6 text-center text-xs uppercase tracking-[0.14em] text-muted">No Stocks Found</div>
              ) : null}
              {filteredStocks.map((stock) => {
                const isChecked = selectedSymbols.includes(stock.ticker) || manualSymbols.includes(stock.ticker);
                return (
                  <label
                    key={stock.ticker}
                    className="grid cursor-pointer grid-cols-[20px_minmax(0,1fr)] gap-2 border-b border-line/70 px-3 py-2 text-xs last:border-b-0 hover:bg-panel"
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => (isChecked ? removeSymbol(stock.ticker) : toggleSymbol(stock.ticker))}
                    />
                    <span className="min-w-0">
                      <span className="font-mono text-text">{stock.ticker}</span>
                      <span className="ml-2 text-muted">{stock.name || "US stock"}</span>
                      {stock.sector ? <span className="ml-2 text-cyan">{stock.sector}</span> : null}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <span className="form-label">Selected Stocks</span>
              <span className="font-mono text-xs text-cyan">{payloadSymbols.length} stocks selected</span>
            </div>
            <div className="flex min-h-9 flex-wrap gap-2">
              {payloadSymbols.length ? (
                payloadSymbols.map((symbol) => (
                  <button
                    key={symbol}
                    className="border border-cyan/60 bg-cyan/10 px-2 py-1 font-mono text-xs text-cyan transition hover:border-red hover:text-red"
                    type="button"
                    onClick={() => removeSymbol(symbol)}
                  >
                    {symbol}
                  </button>
                ))
              ) : (
                <span className="border border-dashed border-line px-3 py-2 text-xs text-muted">No symbols selected</span>
              )}
            </div>
          </div>

          <label className="space-y-2">
            <span className="form-label">Manual Symbols</span>
            <input
              className="form-control font-mono text-xs"
              value={manualSymbolsText}
              onChange={(event) => {
                setManualSymbolsText(event.target.value);
                setSelectionWarning(null);
              }}
              placeholder="AAPL MSFT NVDA GOOGL"
              spellCheck={false}
            />
          </label>
        </>
      ) : (
        <div className="border border-cyan/50 bg-cyan/10 px-3 py-2 text-xs leading-5 text-cyan">
          Sector mode optimizes the selected sector as a portfolio universe.
        </div>
      )}

      {warning ? (
        <div className="border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
          {warning}
        </div>
      ) : null}

      {universeError ? (
        <div className="border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">
          {universeError}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3">
        <label className="space-y-2">
          <span className="form-label">Lookback</span>
          <select className="form-control" value={lookback} onChange={(event) => setLookback(event.target.value as PortfolioOptimizationRequest["lookback"])}>
            {lookbacks.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2">
          <span className="form-label">Objective</span>
          <select className="form-control" value={objective} onChange={(event) => setObjective(event.target.value as PortfolioOptimizationRequest["objective"])}>
            {objectives.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <label className="space-y-2">
          <span className="form-label">Risk-Free</span>
          <input
            className="form-control"
            type="number"
            min={0}
            max={0.25}
            step={0.005}
            value={riskFreeRate}
            onChange={(event) => setRiskFreeRate(Number(event.target.value))}
          />
        </label>

        <label className="space-y-2">
          <span className="form-label">Max Weight</span>
          <input
            className="form-control"
            type="number"
            min={0.05}
            max={1}
            step={0.05}
            value={maxWeight}
            onChange={(event) => setMaxWeight(Number(event.target.value))}
          />
        </label>

        <label className="space-y-2">
          <span className="form-label">Frontier</span>
          <input
            className="form-control"
            type="number"
            min={100}
            max={10000}
            step={100}
            value={frontierPoints}
            onChange={(event) => setFrontierPoints(Number(event.target.value))}
          />
        </label>
      </div>

      <label className="flex items-center justify-between border border-line bg-ink px-3 py-2">
        <span className="form-label">Allow Short</span>
        <input
          type="checkbox"
          checked={allowShort}
          onChange={(event) => setAllowShort(event.target.checked)}
        />
      </label>

      <details className="border border-line bg-ink">
        <summary className="cursor-pointer px-3 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-text">
          Scenario Analysis
        </summary>
        <div className="space-y-4 border-t border-line p-3">
          <label className="flex items-center justify-between gap-3 border border-line bg-panel px-3 py-2">
            <span className="form-label">Enable Scenario Analysis</span>
            <input
              type="checkbox"
              checked={scenarioEnabled}
              onChange={(event) => toggleScenarioEnabled(event.target.checked)}
            />
          </label>

          <div className="space-y-2">
            <span className="form-label">Scenarios</span>
            <div className="grid grid-cols-2 gap-2">
              {scenarioOptions.map((option) => (
                <label
                  key={option.name}
                  className="flex items-center justify-between gap-2 border border-line bg-panel px-3 py-2 text-xs text-text"
                >
                  <span>{option.label}</span>
                  <input
                    type="checkbox"
                    checked={selectedScenarios.includes(option.name)}
                    disabled={!scenarioEnabled}
                    onChange={() => toggleScenario(option.name)}
                  />
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <label className="space-y-2">
              <span className="form-label">Forecast Days</span>
              <input
                className="form-control"
                type="number"
                min={1}
                max={252}
                step={1}
                value={scenarioDays}
                disabled={!scenarioEnabled}
                onChange={(event) => setScenarioDays(Number(event.target.value))}
              />
            </label>
            <label className="space-y-2">
              <span className="form-label">Simulations</span>
              <input
                className="form-control"
                type="number"
                min={100}
                max={5000}
                step={100}
                value={scenarioSimulations}
                disabled={!scenarioEnabled}
                onChange={(event) => setScenarioSimulations(Number(event.target.value))}
              />
            </label>
            <label className="space-y-2">
              <span className="form-label">Block Size</span>
              <input
                className="form-control"
                type="number"
                min={1}
                max={20}
                step={1}
                value={scenarioBlockSize}
                disabled={!scenarioEnabled}
                onChange={(event) => setScenarioBlockSize(Number(event.target.value))}
              />
            </label>
          </div>

          <details className="border border-line bg-panel">
            <summary className="cursor-pointer px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
              Advanced Scenario Assumptions
            </summary>
            <div className="space-y-4 border-t border-line p-3">
              {scenarioOptions.map((option) => (
                <div key={option.name} className="space-y-2 border border-line bg-ink p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text">
                    {option.label} Assumptions
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    {overrideFields.map((field) => (
                      <label key={field.key} className="space-y-2">
                        <span className="form-label">{field.label}</span>
                        <input
                          className="form-control"
                          type="number"
                          min={field.min}
                          max={field.max}
                          step={field.step}
                          value={scenarioOverrides[option.name][field.key] || ""}
                          disabled={!scenarioEnabled}
                          onChange={(event) => updateScenarioOverride(option.name, field.key, event.target.value)}
                          placeholder="Preset"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </details>
        </div>
      </details>

      <button
        className="w-full border border-cyan bg-cyan/15 px-4 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-cyan transition hover:bg-cyan/25 disabled:cursor-not-allowed disabled:border-line disabled:bg-line/30 disabled:text-muted"
        type="submit"
        disabled={!canRun}
      >
        {isLoading || isUniverseLoading ? "Running Optimizer" : "Run Optimization"}
      </button>
    </form>
  );
}

function filterStocks(stocks: StockUniverseItem[], searchText: string): StockUniverseItem[] {
  const query = searchText.trim().toUpperCase();
  if (!query) return stocks;
  return stocks.filter((stock) => {
    const haystack = [stock.ticker, stock.name, stock.sector].join(" ").toUpperCase();
    return haystack.includes(query);
  });
}

function modeButtonClass(isActive: boolean): string {
  return [
    "px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition",
    isActive ? "bg-cyan/15 text-cyan" : "text-muted hover:text-text",
  ].join(" ");
}

function parseSymbols(value: string): string[] {
  return uniqueSymbols(
    value
      .split(/[\s,;]+/g)
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean),
  );
}

function uniqueSymbols(symbols: string[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const symbol of symbols) {
    const cleaned = symbol.includes(":") ? symbol.split(":").pop() || symbol : symbol;
    if (!seen.has(cleaned)) {
      result.push(cleaned);
      seen.add(cleaned);
    }
  }
  return result;
}

function createEmptyScenarioOverrides(): ScenarioOverrideInputs {
  return scenarioOptions.reduce((acc, option) => {
    acc[option.name] = {
      drift_shift_annual: "",
      volatility_multiplier: "",
      initial_shock_pct: "",
    };
    return acc;
  }, {} as ScenarioOverrideInputs);
}

function buildScenarioConfig(
  enabled: boolean,
  selectedScenarios: PortfolioScenarioName[],
  days: number,
  simulations: number,
  blockSize: number,
  overrideInputs: ScenarioOverrideInputs,
): PortfolioMonteCarloConfig {
  const scenarios = selectedScenarios.length ? selectedScenarios : scenarioOptions.map((item) => item.name);
  const scenario_overrides: PortfolioMonteCarloConfig["scenario_overrides"] = {};

  for (const scenario of scenarios) {
    const override: PortfolioScenarioOverride = {};
    for (const field of overrideFields) {
      const rawValue = overrideInputs[scenario][field.key];
      if (rawValue === "") continue;
      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed)) continue;
      (override as Record<string, number>)[field.key] = clampNumber(parsed, field.min, field.max, parsed);
    }
    if (Object.keys(override).length > 0) {
      scenario_overrides[scenario] = override;
    }
  }

  return {
    enabled,
    days: Math.round(clampNumber(days, 1, 252, 60)),
    simulations: Math.round(clampNumber(simulations, 100, 5000, 500)),
    block_size: Math.round(clampNumber(blockSize, 1, 20, 5)),
    seed: 42,
    scenarios,
    scenario_overrides,
  };
}

function clampNumber(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(value, min), max);
}
