import { useEffect, useMemo, useState } from "react";
import {
  fetchSectors,
  fetchStocksBySector,
  fetchStrategyDetails,
  resolveSymbolsForSector,
  type MultiStockResearchRequest,
  type PortfolioOptimizationRequest,
  type RawAssetMonteCarloRequest,
  type ResearchResultEnvelope,
  type SingleStockResearchRequest,
  type StockUniverseItem,
  type StrategyDetails,
  type StrategyRegistryItem,
} from "../../api/client";
import A2UITemplateRenderer from "../../components/A2UITemplateRenderer";

type ManualResearchLabProps = {
  strategies: StrategyRegistryItem[];
  selectedStrategyId?: string;
  isLoading: boolean;
  lastEnvelope: ResearchResultEnvelope | null;
  onRunSingle: (payload: SingleStockResearchRequest) => Promise<void>;
  onRunMulti: (payload: MultiStockResearchRequest) => Promise<void>;
  onRunRawMarkowitz: (payload: PortfolioOptimizationRequest) => Promise<void>;
  onRunRawMonteCarlo: (payload: RawAssetMonteCarloRequest) => Promise<void>;
};

type OptimizerMode = "raw_asset" | "strategy_conditioned";
type Objective = "max_sharpe" | "min_volatility" | "target_return" | "target_volatility";

export default function ManualResearchLab({
  strategies,
  selectedStrategyId,
  isLoading,
  lastEnvelope,
  onRunSingle,
  onRunMulti,
  onRunRawMarkowitz,
  onRunRawMonteCarlo,
}: ManualResearchLabProps) {
  const executableStrategies = useMemo(
    () => strategies.filter((strategy) => strategy.executable || (strategy.runnable && strategy.execution_type === "single_asset_signal")),
    [strategies],
  );
  const [strategyId, setStrategyId] = useState("");
  const [strategyDetails, setStrategyDetails] = useState<StrategyDetails | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [symbolsText, setSymbolsText] = useState("AAPL, MSFT, NVDA, GOOGL");
  const [lookback, setLookback] = useState<"1mo" | "6mo" | "1y" | "2y" | "5y">("2y");
  const [initialCash, setInitialCash] = useState(10000);
  const [fees, setFees] = useState(0.001);
  const [sectors, setSectors] = useState<string[]>([]);
  const [sector, setSector] = useState("");
  const [sectorStocks, setSectorStocks] = useState<StockUniverseItem[]>([]);
  const [selectedSectorSymbols, setSelectedSectorSymbols] = useState<string[]>([]);
  const [optimizerMode, setOptimizerMode] = useState<OptimizerMode>("raw_asset");
  const [objective, setObjective] = useState<Objective>("max_sharpe");
  const [allowShort, setAllowShort] = useState(false);
  const [minWeight, setMinWeight] = useState<number | null>(null);
  const [maxWeight, setMaxWeight] = useState(0.6);
  const [grossExposure, setGrossExposure] = useState(1);
  const [netExposure, setNetExposure] = useState(1);
  const [riskFreeRate, setRiskFreeRate] = useState(0.0);
  const [targetReturn, setTargetReturn] = useState(0.12);
  const [targetVolatility, setTargetVolatility] = useState(0.18);
  const [covarianceRegularization, setCovarianceRegularization] = useState(0.000001);
  const [frontierCount, setFrontierCount] = useState(1000);
  const [mcEnabled, setMcEnabled] = useState(true);
  const [mcMethod, setMcMethod] = useState<"bootstrap" | "block_bootstrap">("bootstrap");
  const [mcDays, setMcDays] = useState(60);
  const [mcSimulations, setMcSimulations] = useState(500);
  const [mcBlockSize, setMcBlockSize] = useState(5);
  const [mcSeed, setMcSeed] = useState<number | null>(42);
  const [lossThresholds, setLossThresholds] = useState("-0.10, -0.20");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedStrategyId) setStrategyId(selectedStrategyId);
  }, [selectedStrategyId]);

  useEffect(() => {
    if (!strategyId && executableStrategies.length) setStrategyId(executableStrategies[0].strategy_id);
  }, [executableStrategies, strategyId]);

  useEffect(() => {
    fetchSectors().then(setSectors).catch((error) => setLocalError(error instanceof Error ? error.message : "Could not load sectors."));
  }, []);

  useEffect(() => {
    if (!sector) return;
    fetchStocksBySector(sector)
      .then((stocks) => {
        setSectorStocks(stocks);
        setSelectedSectorSymbols([]);
      })
      .catch((error) => setLocalError(error instanceof Error ? error.message : "Could not load sector stocks."));
  }, [sector]);

  useEffect(() => {
    if (!strategyId) return;
    let cancelled = false;
    fetchStrategyDetails(strategyId)
      .then((response) => {
        if (cancelled) return;
        const details = response.strategy || null;
        setStrategyDetails(details);
        setParameters(details?.default_parameters || {});
      })
      .catch((error) => {
        if (!cancelled) setLocalError(error instanceof Error ? error.message : "Could not load strategy details.");
      });
    return () => {
      cancelled = true;
    };
  }, [strategyId]);

  const selectedSymbols = useMemo(() => {
    const explicit = parseSymbols(symbolsText);
    return selectedSectorSymbols.length ? selectedSectorSymbols : explicit;
  }, [selectedSectorSymbols, symbolsText]);

  async function handleResolveSector() {
    if (!sector) return;
    setLocalError(null);
    try {
      const response = await resolveSymbolsForSector(sector);
      setSelectedSectorSymbols(response.symbols);
      setSymbolsText(response.symbols.join(", "));
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "Sector resolution failed.");
    }
  }

  async function handleRunBacktest() {
    setLocalError(null);
    if (!strategyId) {
      setLocalError("Select an executable strategy.");
      return;
    }
    if (selectedSymbols.length < 1) {
      setLocalError("Select at least one symbol.");
      return;
    }
    if (selectedSymbols.length === 1) {
      await onRunSingle({
        symbol: selectedSymbols[0],
        strategy_id: strategyId,
        parameters,
        lookback,
        resolution: "D",
        initial_cash: initialCash,
        fees,
        monte_carlo: monteCarloPayload("strategy_returns"),
      });
    } else {
      await onRunMulti({
        symbols: selectedSymbols,
        strategy_id: strategyId,
        parameters,
        lookback,
        resolution: "D",
        initial_cash: initialCash,
        fees,
        optimization: optimizerSettings(),
        monte_carlo: monteCarloPayload("portfolio_returns"),
      });
    }
  }

  async function handleRunOptimizer() {
    setLocalError(null);
    if (selectedSymbols.length < 2) {
      setLocalError("Optimizer requires at least two symbols.");
      return;
    }
    if (optimizerMode === "strategy_conditioned") {
      if (!strategyId) {
        setLocalError("Select an executable strategy for strategy-conditioned Markowitz.");
        return;
      }
      await onRunMulti({
        symbols: selectedSymbols,
        strategy_id: strategyId,
        parameters,
        lookback,
        resolution: "D",
        initial_cash: initialCash,
        fees,
        optimization: optimizerSettings(),
        monte_carlo: monteCarloPayload("portfolio_returns"),
      });
      return;
    }
    await onRunRawMarkowitz(rawPortfolioPayload());
  }

  async function handleRunStandaloneMonteCarlo() {
    const symbol = selectedSymbols[0];
    if (!symbol) {
      setLocalError("Select a symbol for standalone raw-asset Monte Carlo.");
      return;
    }
    await onRunRawMonteCarlo({
      symbol,
      lookback,
      resolution: "D",
      start_value: initialCash,
      days: mcDays,
      simulations: mcSimulations,
      method: mcMethod,
      seed: mcSeed,
    });
  }

  return (
    <div className="space-y-4">
      <section className="panel-shell p-4">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
          <div>
            <h2 className="section-title">Manual Research Lab</h2>
            <div className="mt-2 font-mono text-xs text-muted">{selectedSymbols.length} selected symbols / {executableStrategies.length} executable strategies</div>
          </div>
          <button className="terminal-button terminal-button-green" type="button" disabled={isLoading} onClick={() => void handleRunBacktest()}>
            {selectedSymbols.length > 1 ? "Run Multi-Stock Strategy Workflow" : "Run Single-Stock Research"}
          </button>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]">
          <div className="space-y-4">
            <SectionTitle title="A. Strategy Backtest" />
            <label className="space-y-2">
              <span className="form-label">Symbols</span>
              <textarea className="form-control min-h-20 resize-y font-mono text-xs" value={symbolsText} onChange={(event) => setSymbolsText(event.target.value)} />
            </label>
            <div className="grid gap-3 md:grid-cols-4">
              <Select label="Lookback" value={lookback} options={["1mo", "6mo", "1y", "2y", "5y"]} onChange={(value) => setLookback(value as typeof lookback)} />
              <NumberInput label="Initial Capital" value={initialCash} min={1} onChange={setInitialCash} />
              <NumberInput label="Fees" value={fees} min={0} step={0.0005} onChange={setFees} />
              <div className="border border-line bg-ink p-3 font-mono text-xs text-muted">Resolution: D</div>
            </div>
            <label className="space-y-2">
              <span className="form-label">Strategy</span>
              <select className="form-control font-mono" value={strategyId} onChange={(event) => setStrategyId(event.target.value)}>
                {executableStrategies.map((strategy) => (
                  <option key={strategy.strategy_id} value={strategy.strategy_id}>
                    {strategy.name} / {strategy.strategy_id}
                  </option>
                ))}
              </select>
            </label>
            <ParameterEditor strategy={strategyDetails} parameters={parameters} onChange={setParameters} />
          </div>

          <SectorCollection
            sectors={sectors}
            sector={sector}
            stocks={sectorStocks}
            selected={selectedSectorSymbols}
            onSectorChange={setSector}
            onSelectedChange={(symbols) => {
              setSelectedSectorSymbols(symbols);
              if (symbols.length) setSymbolsText(symbols.join(", "));
            }}
            onResolve={() => void handleResolveSector()}
          />
        </div>
      </section>

      <section className="panel-shell p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
          <SectionTitle title="C. Portfolio Optimizer" />
          <button className="terminal-button terminal-button-green" type="button" disabled={isLoading} onClick={() => void handleRunOptimizer()}>
            Run {optimizerMode === "raw_asset" ? "Raw Asset" : "Strategy-Conditioned"} Markowitz
          </button>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <ModeButton active={optimizerMode === "raw_asset"} label="Raw Asset Markowitz" onClick={() => setOptimizerMode("raw_asset")} />
              <ModeButton active={optimizerMode === "strategy_conditioned"} label="Strategy-Conditioned Markowitz" onClick={() => setOptimizerMode("strategy_conditioned")} />
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <Select label="Objective" value={objective} options={["max_sharpe", "min_volatility", "target_return", "target_volatility"]} onChange={(value) => setObjective(value as Objective)} />
              <NumberInput label="Risk-Free Rate" value={riskFreeRate} min={0} max={0.25} step={0.001} onChange={setRiskFreeRate} />
              <NumberInput label="Frontier Portfolios" value={frontierCount} min={50} max={10000} step={50} onChange={setFrontierCount} />
              <NumberInput label="Target Return" value={targetReturn} step={0.01} onChange={setTargetReturn} />
              <NumberInput label="Target Volatility" value={targetVolatility} step={0.01} onChange={setTargetVolatility} />
              <NumberInput label="Cov Regularization" value={covarianceRegularization} min={0} step={0.000001} onChange={setCovarianceRegularization} />
            </div>
          </div>
          <div className="space-y-4">
            <label className="flex items-center gap-3 border border-line bg-ink px-3 py-2 text-xs text-muted">
              <input type="checkbox" checked={allowShort} onChange={(event) => setAllowShort(event.target.checked)} />
              Bounded long-short
            </label>
            <div className="grid gap-3 md:grid-cols-4">
              <NullableNumberInput label="Min Weight" value={minWeight} onChange={setMinWeight} />
              <NumberInput label="Max Weight" value={maxWeight} min={0.01} max={1} step={0.01} onChange={setMaxWeight} />
              <NumberInput label="Gross Exposure" value={grossExposure} min={0.01} max={3} step={0.05} onChange={setGrossExposure} />
              <NumberInput label="Net Exposure" value={netExposure} min={-1} max={1} step={0.05} onChange={setNetExposure} />
            </div>
            <div className="border border-line bg-ink p-3 text-xs leading-5 text-muted">
              {optimizerMode === "raw_asset"
                ? "Uses historical asset return streams directly."
                : "Runs the selected strategy on each symbol first, then optimizes strategy return streams."}
            </div>
          </div>
        </div>
      </section>

      <section className="panel-shell p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
          <SectionTitle title="D. Monte Carlo" />
          <button className="terminal-button" type="button" disabled={isLoading} onClick={() => void handleRunStandaloneMonteCarlo()}>
            Run Standalone Raw-Asset Monte Carlo
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-6">
          <label className="flex items-center gap-3 border border-line bg-ink px-3 py-2 text-xs text-muted">
            <input type="checkbox" checked={mcEnabled} onChange={(event) => setMcEnabled(event.target.checked)} />
            Enabled in workflows
          </label>
          <Select label="Method" value={mcMethod} options={["bootstrap", "block_bootstrap"]} onChange={(value) => setMcMethod(value as typeof mcMethod)} />
          <NumberInput label="Horizon Days" value={mcDays} min={1} max={252} onChange={setMcDays} />
          <NumberInput label="Simulations" value={mcSimulations} min={10} max={5000} step={10} onChange={setMcSimulations} />
          <NumberInput label="Block Size" value={mcBlockSize} min={1} max={20} onChange={setMcBlockSize} />
          <NullableNumberInput label="Seed" value={mcSeed} onChange={setMcSeed} />
        </div>
        <label className="mt-3 block space-y-2">
          <span className="form-label">Loss Thresholds</span>
          <input className="form-control font-mono" value={lossThresholds} onChange={(event) => setLossThresholds(event.target.value)} />
        </label>
      </section>

      {localError ? <div className="border border-red/60 bg-red/10 p-3 text-sm text-red">{localError}</div> : null}
      {lastEnvelope ? <A2UITemplateRenderer envelope={lastEnvelope} /> : null}
    </div>
  );

  function optimizerSettings() {
    return {
      objective,
      risk_free_rate: riskFreeRate,
      target_return: objective === "target_return" ? targetReturn : null,
      target_volatility: objective === "target_volatility" ? targetVolatility : null,
      allow_short: allowShort,
      min_weight: minWeight,
      max_weight: maxWeight,
      gross_exposure_limit: grossExposure,
      net_exposure: netExposure,
      covariance_regularization: covarianceRegularization,
      num_frontier_portfolios: frontierCount,
    };
  }

  function rawPortfolioPayload(): PortfolioOptimizationRequest {
    return {
      symbols: selectedSymbols,
      sector: selectedSectorSymbols.length ? sector : undefined,
      lookback,
      resolution: "D",
      initial_cash: initialCash,
      fees,
      ...optimizerSettings(),
      monte_carlo: {
        ...monteCarloPayload("portfolio_returns"),
        days: mcDays,
        block_size: mcBlockSize,
        scenarios: ["neutral", "bullish", "bearish", "crash"],
        scenario_overrides: {},
      } as PortfolioOptimizationRequest["monte_carlo"],
    };
  }

  function monteCarloPayload<T extends "strategy_returns" | "portfolio_returns">(mode: T) {
    return {
      enabled: mcEnabled,
      method: mcMethod,
      mode,
      days: mcDays,
      simulations: mcSimulations,
      block_size: mcBlockSize,
      seed: mcSeed,
      thresholds: parseThresholds(lossThresholds),
    };
  }
}

function SectorCollection({
  sectors,
  sector,
  stocks,
  selected,
  onSectorChange,
  onSelectedChange,
  onResolve,
}: {
  sectors: string[];
  sector: string;
  stocks: StockUniverseItem[];
  selected: string[];
  onSectorChange: (sector: string) => void;
  onSelectedChange: (symbols: string[]) => void;
  onResolve: () => void;
}) {
  const selectedSet = new Set(selected);
  const allSymbols = stocks.map((stock) => stock.ticker).filter(Boolean) as string[];
  return (
    <div className="space-y-4">
      <SectionTitle title="B. Sector-Wise Stock Collection" />
      <Select label="Sector" value={sector} options={["", ...sectors]} onChange={onSectorChange} />
      <div className="flex flex-wrap gap-2">
        <button className="terminal-button" type="button" disabled={!stocks.length} onClick={() => onSelectedChange(allSymbols)}>
          Select All Sector Stocks
        </button>
        <button className="terminal-button" type="button" disabled={!sector} onClick={onResolve}>
          Resolve Sector Symbols Through MCP
        </button>
        <button className="terminal-button" type="button" onClick={() => onSelectedChange([])}>
          Clear Sector Selection
        </button>
      </div>
      <div className="max-h-80 overflow-auto border border-line">
        <table className="min-w-full border-collapse font-mono text-xs">
          <thead className="bg-panel2 text-muted">
            <tr>
              <th className="border-b border-line px-3 py-2 text-left">Use</th>
              <th className="border-b border-line px-3 py-2 text-left">Ticker</th>
              <th className="border-b border-line px-3 py-2 text-left">Name</th>
              <th className="border-b border-line px-3 py-2 text-left">Risk</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock) => {
              const ticker = stock.ticker || "";
              return (
                <tr key={ticker} className="odd:bg-ink even:bg-panel">
                  <td className="border-b border-line px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selectedSet.has(ticker)}
                      onChange={(event) => {
                        onSelectedChange(event.target.checked ? [...selected, ticker] : selected.filter((item) => item !== ticker));
                      }}
                    />
                  </td>
                  <td className="border-b border-line px-3 py-2 text-green">{ticker}</td>
                  <td className="border-b border-line px-3 py-2 text-muted">{stock.name}</td>
                  <td className="border-b border-line px-3 py-2 text-muted">{stock.risk_level || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="font-mono text-xs text-muted">{selected.length} sector symbols selected for backtest, optimizer, and Monte Carlo workflows.</div>
    </div>
  );
}

function ParameterEditor({
  strategy,
  parameters,
  onChange,
}: {
  strategy: StrategyDetails | null;
  parameters: Record<string, unknown>;
  onChange: (parameters: Record<string, unknown>) => void;
}) {
  const properties = objectValue(strategy?.parameter_schema?.properties);
  if (!properties || !Object.keys(properties).length) {
    return <div className="border border-line bg-ink p-3 text-xs text-muted">No editable strategy parameters returned.</div>;
  }
  return (
    <div className="space-y-3">
      <span className="form-label">Strategy Parameters</span>
      <div className="grid gap-3 md:grid-cols-3">
        {Object.entries(properties).map(([name, schema]) => (
          <ParameterInput
            key={name}
            name={name}
            schema={objectValue(schema) || {}}
            value={parameters[name]}
            onChange={(value) => onChange({ ...parameters, [name]: value })}
          />
        ))}
      </div>
    </div>
  );
}

function ParameterInput({
  name,
  schema,
  value,
  onChange,
}: {
  name: string;
  schema: Record<string, unknown>;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const enumValues = Array.isArray(schema.enum) ? schema.enum.map(String) : [];
  const type = String(schema.type || "number");
  if (enumValues.length) {
    return <Select label={name} value={String(value ?? schema.default ?? enumValues[0])} options={enumValues} onChange={onChange} />;
  }
  if (type === "boolean") {
    return (
      <label className="flex items-center gap-3 border border-line bg-ink px-3 py-2 text-xs text-muted">
        <input type="checkbox" checked={Boolean(value ?? schema.default)} onChange={(event) => onChange(event.target.checked)} />
        {name}
      </label>
    );
  }
  if (type === "integer" || type === "number") {
    return (
      <NumberInput
        label={name}
        value={Number(value ?? schema.default ?? 0)}
        min={typeof schema.minimum === "number" ? schema.minimum : undefined}
        max={typeof schema.maximum === "number" ? schema.maximum : undefined}
        step={type === "integer" ? 1 : 0.01}
        onChange={onChange}
      />
    );
  }
  return (
    <label className="space-y-2">
      <span className="form-label">{name}</span>
      <input className="form-control font-mono" value={String(value ?? schema.default ?? "")} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h3 className="section-title">{title}</h3>;
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="space-y-2">
      <span className="form-label">{label}</span>
      <select className="form-control font-mono" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option || "empty"} value={option}>
            {option ? option.replace(/_/g, " ") : "Select"}
          </option>
        ))}
      </select>
    </label>
  );
}

function NumberInput({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="space-y-2">
      <span className="form-label">{label}</span>
      <input className="form-control font-mono" type="number" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function NullableNumberInput({ label, value, onChange }: { label: string; value: number | null; onChange: (value: number | null) => void }) {
  return (
    <label className="space-y-2">
      <span className="form-label">{label}</span>
      <input className="form-control font-mono" value={value ?? ""} onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))} />
    </label>
  );
}

function ModeButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button className={`border px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${active ? "border-green bg-green/15 text-green" : "border-line bg-ink text-muted hover:border-muted"}`} type="button" onClick={onClick}>
      {label}
    </button>
  );
}

function parseSymbols(value: string): string[] {
  return value
    .split(/[\s,;]+/)
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean)
    .filter((symbol, index, symbols) => symbols.indexOf(symbol) === index);
}

function parseThresholds(value: string): number[] {
  const parsed = value
    .split(/[\s,;]+/)
    .map(Number)
    .filter(Number.isFinite);
  return parsed.length ? parsed : [-0.1, -0.2];
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}
