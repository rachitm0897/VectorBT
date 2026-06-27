import { useEffect, useMemo, useState } from "react";
import {
  fetchSectors,
  type FactorModelConfiguration,
  type FactorPortfolioRequest,
  type PortfolioScenarioName,
} from "../api/client";

type FactorPortfolioPanelProps = {
  isLoading: boolean;
  onSubmit: (payload: FactorPortfolioRequest) => void;
};

const scenarios: Array<{ name: PortfolioScenarioName; label: string }> = [
  { name: "neutral", label: "Neutral" },
  { name: "bullish", label: "Bullish" },
  { name: "bearish", label: "Bearish" },
  { name: "crash", label: "Crash" },
];

export default function FactorPortfolioPanel({ isLoading, onSubmit }: FactorPortfolioPanelProps) {
  const [step, setStep] = useState(1);
  const [selectionMode, setSelectionMode] = useState<"symbols" | "sector">("sector");
  const [sectors, setSectors] = useState<string[]>([]);
  const [sector, setSector] = useState("Technology");
  const [symbolsText, setSymbolsText] = useState("AAPL MSFT NVDA GOOGL META");
  const [normalizationMode, setNormalizationMode] = useState<"universe" | "sector">("sector");
  const [weights, setWeights] = useState({
    fundamental_quality: 30,
    valuation: 20,
    momentum: 20,
    analyst: 15,
    financial_risk: 15,
  });
  const [minimumCoverage, setMinimumCoverage] = useState(60);
  const [selectionMethod, setSelectionMethod] = useState<FactorModelConfiguration["selection_method"]>("top_n");
  const [topN, setTopN] = useState(10);
  const [topPercentile, setTopPercentile] = useState(30);
  const [minimumScore, setMinimumScore] = useState(65);
  const [objective, setObjective] = useState<"max_sharpe" | "min_volatility">("max_sharpe");
  const [expectedReturnMethod, setExpectedReturnMethod] = useState<"historical" | "factor_tilted">("historical");
  const [maximumWeight, setMaximumWeight] = useState(0.25);
  const [riskFreeRate, setRiskFreeRate] = useState(0.04);
  const [tiltStrength, setTiltStrength] = useState(0.2);
  const [tiltCap, setTiltCap] = useState(0.05);
  const [scenarioEnabled, setScenarioEnabled] = useState(true);
  const [scenarioDays, setScenarioDays] = useState(60);
  const [scenarioSimulations, setScenarioSimulations] = useState(500);
  const [scenarioBlockSize, setScenarioBlockSize] = useState(5);
  const [selectedScenarios, setSelectedScenarios] = useState<PortfolioScenarioName[]>(scenarios.map((item) => item.name));
  const [universeError, setUniverseError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSectors()
      .then((items) => {
        if (cancelled) return;
        setSectors(items);
        setSector((current) => current || items[0] || "");
      })
      .catch((error) => {
        if (!cancelled) setUniverseError(error instanceof Error ? error.message : "Could not load sectors.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const symbols = useMemo(() => parseSymbols(symbolsText), [symbolsText]);
  const weightSum = Object.values(weights).reduce((sum, value) => sum + value, 0);
  const weightsValid = Math.abs(weightSum - 100) < 0.001;
  const canRun = !isLoading && weightsValid && (selectionMode === "sector" ? Boolean(sector) : symbols.length >= 2);

  function submit() {
    if (!canRun) return;
    onSubmit({
      symbols: selectionMode === "symbols" ? symbols : [],
      sector: selectionMode === "sector" ? sector : undefined,
      selection_mode: selectionMode,
      lookback: "2y",
      resolution: "D",
      factor_model: {
        enabled: true,
        normalization_mode: normalizationMode,
        weights: {
          fundamental_quality: weights.fundamental_quality / 100,
          valuation: weights.valuation / 100,
          momentum: weights.momentum / 100,
          analyst: weights.analyst / 100,
          financial_risk: weights.financial_risk / 100,
        },
        minimum_data_coverage_pct: clamp(minimumCoverage, 0, 100),
        selection_method: selectionMethod,
        top_n: Math.round(clamp(topN, 1, 50)),
        top_percentile: clamp(topPercentile, 1, 100),
        minimum_score: selectionMethod === "minimum_score" ? clamp(minimumScore, 0, 100) : null,
      },
      optimization: {
        objective,
        minimum_weight: 0,
        maximum_weight: clamp(maximumWeight, 0.05, 1),
        risk_free_rate: clamp(riskFreeRate, 0, 0.25),
        expected_return_method: expectedReturnMethod,
      },
      score_tilt: {
        enabled: expectedReturnMethod === "factor_tilted",
        strength: clamp(tiltStrength, 0, 1),
        maximum_adjustment_pct: clamp(tiltCap, 0, 0.5),
      },
      monte_carlo: {
        enabled: scenarioEnabled,
        days: Math.round(clamp(scenarioDays, 1, 252)),
        simulations: Math.round(clamp(scenarioSimulations, 100, 5000)),
        block_size: Math.round(clamp(scenarioBlockSize, 1, 20)),
        seed: 42,
        scenarios: selectedScenarios.length ? selectedScenarios : ["neutral"],
        scenario_overrides: {},
      },
    });
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="grid grid-cols-5 border border-line bg-ink p-1">
        {[1, 2, 3, 4, 5].map((item) => (
          <button key={item} type="button" className={stepClass(step === item)} onClick={() => setStep(item)}>
            {item}
          </button>
        ))}
      </div>

      {step === 1 ? (
        <div className="space-y-3">
          <StepTitle title="1. Select Universe" />
          <div className="grid grid-cols-2 border border-line bg-ink p-1">
            <button type="button" className={modeButtonClass(selectionMode === "sector")} onClick={() => setSelectionMode("sector")}>
              Sector
            </button>
            <button type="button" className={modeButtonClass(selectionMode === "symbols")} onClick={() => setSelectionMode("symbols")}>
              Symbols
            </button>
          </div>
          {selectionMode === "sector" ? (
            <label className="space-y-2">
              <span className="form-label">Sector</span>
              <select className="form-control" value={sector} onChange={(event) => setSector(event.target.value)}>
                {sectors.length ? null : <option value={sector}>{sector || "Loading sectors"}</option>}
                {sectors.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="space-y-2">
              <span className="form-label">Symbols</span>
              <input className="form-control font-mono text-xs" value={symbolsText} onChange={(event) => setSymbolsText(event.target.value)} />
            </label>
          )}
          {universeError ? <Warning message={universeError} /> : null}
        </div>
      ) : null}

      {step === 2 ? (
        <div className="space-y-3">
          <StepTitle title="2. Configure Factor Model" />
          <label className="space-y-2">
            <span className="form-label">Normalisation Mode</span>
            <select className="form-control" value={normalizationMode} onChange={(event) => setNormalizationMode(event.target.value as "universe" | "sector")}>
              <option value="sector">Sector</option>
              <option value="universe">Universe</option>
            </select>
          </label>
          {Object.entries(weights).map(([key, value]) => (
            <label key={key} className="space-y-2">
              <span className="form-label">{factorLabel(key)} Weight</span>
              <input className="form-control" type="number" min={0} max={100} step={1} value={value} onChange={(event) => setWeights((current) => ({ ...current, [key]: Number(event.target.value) }))} />
            </label>
          ))}
          <div className={weightsValid ? "border border-green/60 bg-green/10 px-3 py-2 text-xs text-green" : "border border-red/60 bg-red/10 px-3 py-2 text-xs text-red"}>
            Factor weights total {weightSum.toFixed(1)}%.
          </div>
          <label className="space-y-2">
            <span className="form-label">Minimum Data Coverage</span>
            <input className="form-control" type="number" min={0} max={100} value={minimumCoverage} onChange={(event) => setMinimumCoverage(Number(event.target.value))} />
          </label>
          <label className="space-y-2">
            <span className="form-label">Selection Method</span>
            <select className="form-control" value={selectionMethod} onChange={(event) => setSelectionMethod(event.target.value as FactorModelConfiguration["selection_method"])}>
              <option value="top_n">Top N</option>
              <option value="top_percentile">Top Percentile</option>
              <option value="minimum_score">Minimum Score</option>
              <option value="all_eligible">All Eligible</option>
            </select>
          </label>
          {selectionMethod === "top_n" ? <NumberField label="Top N" value={topN} onChange={setTopN} min={1} max={50} /> : null}
          {selectionMethod === "top_percentile" ? <NumberField label="Top Percentile" value={topPercentile} onChange={setTopPercentile} min={1} max={100} /> : null}
          {selectionMethod === "minimum_score" ? <NumberField label="Minimum Combined Score" value={minimumScore} onChange={setMinimumScore} min={0} max={100} /> : null}
        </div>
      ) : null}

      {step === 3 ? (
        <div className="space-y-3">
          <StepTitle title="3. Configure Portfolio Optimisation" />
          <label className="space-y-2">
            <span className="form-label">Objective</span>
            <select className="form-control" value={objective} onChange={(event) => setObjective(event.target.value as "max_sharpe" | "min_volatility")}>
              <option value="max_sharpe">Maximum Sharpe</option>
              <option value="min_volatility">Minimum Volatility</option>
            </select>
          </label>
          <label className="space-y-2">
            <span className="form-label">Expected Returns</span>
            <select className="form-control" value={expectedReturnMethod} onChange={(event) => setExpectedReturnMethod(event.target.value as "historical" | "factor_tilted")}>
              <option value="historical">Historical</option>
              <option value="factor_tilted">Factor Tilted</option>
            </select>
          </label>
          <NumberField label="Maximum Weight" value={maximumWeight} onChange={setMaximumWeight} min={0.05} max={1} step={0.05} />
          <NumberField label="Risk-Free Rate" value={riskFreeRate} onChange={setRiskFreeRate} min={0} max={0.25} step={0.005} />
          {expectedReturnMethod === "factor_tilted" ? (
            <>
              <NumberField label="Factor-Tilt Strength" value={tiltStrength} onChange={setTiltStrength} min={0} max={1} step={0.05} />
              <NumberField label="Max Return Adjustment" value={tiltCap} onChange={setTiltCap} min={0} max={0.5} step={0.01} />
            </>
          ) : null}
        </div>
      ) : null}

      {step === 4 ? (
        <div className="space-y-3">
          <StepTitle title="4. Configure Scenarios" />
          <label className="flex items-center justify-between border border-line bg-ink px-3 py-2">
            <span className="form-label">Run Scenarios</span>
            <input type="checkbox" checked={scenarioEnabled} onChange={(event) => setScenarioEnabled(event.target.checked)} />
          </label>
          <div className="grid grid-cols-2 gap-2">
            {scenarios.map((scenario) => (
              <label key={scenario.name} className="flex items-center justify-between border border-line bg-ink px-3 py-2 text-xs">
                <span>{scenario.label}</span>
                <input type="checkbox" checked={selectedScenarios.includes(scenario.name)} onChange={() => toggleScenario(scenario.name, selectedScenarios, setSelectedScenarios)} />
              </label>
            ))}
          </div>
          <NumberField label="Days" value={scenarioDays} onChange={setScenarioDays} min={1} max={252} />
          <NumberField label="Simulations" value={scenarioSimulations} onChange={setScenarioSimulations} min={100} max={5000} step={100} />
          <NumberField label="Block Size" value={scenarioBlockSize} onChange={setScenarioBlockSize} min={1} max={20} />
        </div>
      ) : null}

      {step === 5 ? (
        <div className="space-y-3">
          <StepTitle title="5. Review Configuration" />
          <div className="space-y-2">
            <ReviewRow label="Universe" value={selectionMode === "sector" ? sector : symbols.join(", ")} />
            <ReviewRow label="Factor Weights" value={`Quality ${weights.fundamental_quality}%, Valuation ${weights.valuation}%, Momentum ${weights.momentum}%, Analyst ${weights.analyst}%, Risk ${weights.financial_risk}%`} />
            <ReviewRow label="Selection" value={selectionMethod === "top_n" ? `Top ${topN}` : selectionMethod === "top_percentile" ? `Top ${topPercentile}%` : selectionMethod === "minimum_score" ? `Minimum score ${minimumScore}` : "All eligible"} />
            <ReviewRow label="Optimization" value={`${objective.replace(/_/g, " ")} using ${expectedReturnMethod.replace(/_/g, " ")} returns`} />
            <ReviewRow label="Scenarios" value={scenarioEnabled ? selectedScenarios.map((item) => scenarioLabel(item)).join(", ") : "Disabled"} />
          </div>
        </div>
      ) : null}

      <button className="w-full border border-cyan bg-cyan/15 px-4 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-cyan transition hover:bg-cyan/25 disabled:cursor-not-allowed disabled:border-line disabled:bg-line/30 disabled:text-muted" type="submit" disabled={!canRun}>
        {isLoading ? "Constructing Factor Portfolio" : "Construct Factor Portfolio"}
      </button>
    </form>
  );
}

function StepTitle({ title }: { title: string }) {
  return <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text">{title}</div>;
}

function NumberField({ label, value, onChange, min, max, step = 1 }: { label: string; value: number; onChange: (value: number) => void; min: number; max: number; step?: number }) {
  return (
    <label className="space-y-2">
      <span className="form-label">{label}</span>
      <input className="form-control" type="number" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function Warning({ message }: { message: string }) {
  return <div className="border border-amber/60 bg-amber/10 px-3 py-2 text-xs leading-5 text-amber">{message}</div>;
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border border-line bg-ink px-3 py-2 text-xs">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</span>
      <span className="max-w-[70%] text-right text-text">{value || "-"}</span>
    </div>
  );
}

function stepClass(active: boolean): string {
  return ["px-2 py-2 text-xs font-semibold transition", active ? "bg-cyan/15 text-cyan" : "text-muted hover:text-text"].join(" ");
}

function modeButtonClass(active: boolean): string {
  return ["px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition", active ? "bg-cyan/15 text-cyan" : "text-muted hover:text-text"].join(" ");
}

function parseSymbols(value: string): string[] {
  return Array.from(new Set(value.split(/[\s,;]+/g).map((item) => item.trim().toUpperCase()).filter(Boolean)));
}

function factorLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function scenarioLabel(value: PortfolioScenarioName): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

function toggleScenario(
  scenario: PortfolioScenarioName,
  selected: PortfolioScenarioName[],
  setSelected: (value: PortfolioScenarioName[]) => void,
) {
  if (selected.includes(scenario)) {
    if (selected.length === 1) return;
    setSelected(selected.filter((item) => item !== scenario));
  } else {
    setSelected([...selected, scenario]);
  }
}
