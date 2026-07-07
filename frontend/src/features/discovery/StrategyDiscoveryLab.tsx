import { useMemo, useState } from "react";
import {
  discoverStrategyCandidates,
  processApprovedStrategy,
  reviewStrategyCandidate,
  type StrategyCandidate,
  type StrategyRegistryItem,
  type StrategyRegistrySummary,
} from "../../api/client";
import StrategyRegistryTable from "../strategies/StrategyRegistryTable";

type StrategyDiscoveryLabProps = {
  strategies: StrategyRegistryItem[];
  summary: StrategyRegistrySummary | null;
  isRegistryLoading: boolean;
  registryError: string | null;
  onRefreshRegistry: () => void;
  onSyncRegistry: () => void;
  onUseStrategy: (strategyId: string) => void;
};

const sourceOptions = ["openalex", "crossref", "arxiv"];

export default function StrategyDiscoveryLab({
  strategies,
  summary,
  isRegistryLoading,
  registryError,
  onRefreshRegistry,
  onSyncRegistry,
  onUseStrategy,
}: StrategyDiscoveryLabProps) {
  const [query, setQuery] = useState("equity momentum reversal risk adjusted strategy");
  const [sources, setSources] = useState<string[]>(["openalex", "crossref", "arxiv"]);
  const [maxResultsPerSource, setMaxResultsPerSource] = useState(5);
  const [maxCandidates, setMaxCandidates] = useState(10);
  const [startYear, setStartYear] = useState("");
  const [endYear, setEndYear] = useState("");
  const [useLlmExtraction, setUseLlmExtraction] = useState(true);
  const [candidates, setCandidates] = useState<StrategyCandidate[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [editJson, setEditJson] = useState("{}");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [processingWarning, setProcessingWarning] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () => candidates.find((candidate, index) => candidateId(candidate, index) === selectedId) || null,
    [candidates, selectedId],
  );
  const duplicateWarnings = useMemo(() => duplicateRows(candidates), [candidates]);

  async function handleSearch() {
    setBusy(true);
    setError(null);
    setMessage(null);
    setProcessingWarning(null);
    try {
      const response = await discoverStrategyCandidates({
        query,
        sources,
        max_results_per_source: maxResultsPerSource,
        max_candidates: maxCandidates,
        start_year: startYear ? Number(startYear) : null,
        end_year: endYear ? Number(endYear) : null,
      });
      const rows = response.candidates || [];
      setCandidates(rows);
      const firstId = rows[0] ? candidateId(rows[0], 0) : "";
      setSelectedId(firstId);
      setEditJson(firstId ? JSON.stringify(rows[0], null, 2) : "{}");
      setMessage(`Loaded ${response.count ?? rows.length} candidates. LLM extraction ${useLlmExtraction ? "enabled" : "not requested in UI"}.`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Discovery failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReview(action: "approve" | "reject" | "mark_duplicate" | "request_changes") {
    if (!selectedId) {
      setError("Select a candidate first.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await reviewStrategyCandidate(selectedId, {
        action,
        reviewer: "frontend",
        reviewer_note: reviewNote,
        edits: parseEdits(editJson),
      });
      setMessage(`Candidate ${action.replace(/_/g, " ")} recorded.`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Candidate review failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleProcess() {
    if (!selectedId) {
      setError("Select an approved candidate first.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    setProcessingWarning(null);
    try {
      const response = await processApprovedStrategy(selectedId);
      const text = String(response.message || "Approved candidate processed.");
      if (text.includes("approved_processing_not_configured") || JSON.stringify(response).includes("approved_processing_not_configured")) {
        setProcessingWarning("Approved processing is not configured. No backtest, classification, or promotion was performed.");
      }
      setMessage(text);
    } catch (error) {
      const text = error instanceof Error ? error.message : "Approved candidate processing failed.";
      if (text.includes("approved_processing_not_configured")) {
        setProcessingWarning("Approved processing is not configured. No backtest, classification, or promotion was performed.");
      } else {
        setError(text);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <StrategyRegistryTable
        strategies={strategies}
        summary={summary}
        isLoading={isRegistryLoading}
        error={registryError}
        onRefresh={onRefreshRegistry}
        onSync={onSyncRegistry}
        onSelectStrategy={onUseStrategy}
      />

      <section className="panel-shell">
        <div className="border-b border-line p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="section-title">Strategy Candidate Discovery</h2>
              <div className="mt-2 font-mono text-xs text-muted">Research source search, extraction, review, processing, classification, and promotion workspace.</div>
            </div>
            <button className="terminal-button terminal-button-green" type="button" disabled={busy || !query.trim() || !sources.length} onClick={() => void handleSearch()}>
              {busy ? "Running" : "Search Sources"}
            </button>
          </div>
        </div>

        <div className="grid gap-4 p-4 xl:grid-cols-[420px_minmax(0,1fr)]">
          <div className="space-y-4">
            <label className="space-y-2">
              <span className="form-label">Query</span>
              <textarea className="form-control min-h-28 resize-y text-sm leading-6" value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <div className="grid grid-cols-3 gap-2">
              {sourceOptions.map((source) => (
                <label key={source} className="flex items-center gap-2 border border-line bg-ink px-3 py-2 font-mono text-xs text-muted">
                  <input
                    type="checkbox"
                    checked={sources.includes(source)}
                    onChange={(event) => {
                      setSources((current) => (event.target.checked ? [...current, source] : current.filter((item) => item !== source)));
                    }}
                  />
                  {source}
                </label>
              ))}
            </div>
            <label className="flex items-center gap-2 border border-line bg-ink px-3 py-2 text-xs text-muted">
              <input type="checkbox" checked={useLlmExtraction} onChange={(event) => setUseLlmExtraction(event.target.checked)} />
              LLM extraction controls enabled
            </label>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput label="Results / Source" value={maxResultsPerSource} min={1} max={25} onChange={setMaxResultsPerSource} />
              <NumberInput label="Max Candidates" value={maxCandidates} min={1} max={50} onChange={setMaxCandidates} />
              <TextInput label="Start Year" value={startYear} onChange={setStartYear} />
              <TextInput label="End Year" value={endYear} onChange={setEndYear} />
            </div>
            <Warnings duplicateWarnings={duplicateWarnings} processingWarning={processingWarning} error={error} message={message} />
          </div>

          <div className="grid min-h-[620px] gap-4 lg:grid-cols-[minmax(0,1fr)_390px]">
            <CandidateTable candidates={candidates} selectedId={selectedId} onSelect={(candidate, index) => {
              const id = candidateId(candidate, index);
              setSelectedId(id);
              setEditJson(JSON.stringify(candidate, null, 2));
            }} />
            <CandidateDetail
              candidate={selected}
              selectedId={selectedId}
              note={reviewNote}
              editJson={editJson}
              busy={busy}
              onNoteChange={setReviewNote}
              onEditJsonChange={setEditJson}
              onReview={(action) => void handleReview(action)}
              onProcess={() => void handleProcess()}
            />
          </div>
        </div>
      </section>
    </div>
  );
}

function CandidateTable({
  candidates,
  selectedId,
  onSelect,
}: {
  candidates: StrategyCandidate[];
  selectedId: string;
  onSelect: (candidate: StrategyCandidate, index: number) => void;
}) {
  return (
    <div className="overflow-auto border border-line">
      <table className="min-w-full border-collapse font-mono text-xs">
        <thead className="sticky top-0 bg-panel2 text-muted">
          <tr>
            <th className="border-b border-line px-3 py-2 text-left">ID</th>
            <th className="border-b border-line px-3 py-2 text-left">Candidate</th>
            <th className="border-b border-line px-3 py-2 text-left">Implementability</th>
            <th className="border-b border-line px-3 py-2 text-left">Duplicate</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate, index) => {
            const id = candidateId(candidate, index);
            return (
              <tr key={id} className={`cursor-pointer odd:bg-ink even:bg-panel ${selectedId === id ? "outline outline-1 outline-green" : ""}`} onClick={() => onSelect(candidate, index)}>
                <td className="border-b border-line px-3 py-2 text-green">{id}</td>
                <td className="border-b border-line px-3 py-2 text-text">
                  <div>{String(candidate.title || candidate.name || candidate.strategy_name || "Untitled")}</div>
                  <div className="mt-1 max-w-2xl truncate text-muted">{String(candidate.abstract || candidate.description || candidate.summary || "")}</div>
                </td>
                <td className="border-b border-line px-3 py-2 text-muted">{String(candidate.implementability_status || candidate.implementability || candidate.status || "unknown")}</td>
                <td className="border-b border-line px-3 py-2 text-muted">{String(candidate.duplicate_warning || candidate.duplicate_status || "none")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!candidates.length ? <div className="p-6 text-sm text-muted">No candidates loaded.</div> : null}
    </div>
  );
}

function CandidateDetail({
  candidate,
  selectedId,
  note,
  editJson,
  busy,
  onNoteChange,
  onEditJsonChange,
  onReview,
  onProcess,
}: {
  candidate: StrategyCandidate | null;
  selectedId: string;
  note: string;
  editJson: string;
  busy: boolean;
  onNoteChange: (value: string) => void;
  onEditJsonChange: (value: string) => void;
  onReview: (action: "approve" | "reject" | "mark_duplicate" | "request_changes") => void;
  onProcess: () => void;
}) {
  return (
    <aside className="space-y-4 overflow-auto border border-line bg-panel p-4">
      <h3 className="section-title">Candidate Detail</h3>
      {candidate ? (
        <>
          <KeyValue label="Candidate ID" value={selectedId} />
          <KeyValue label="Implementability" value={String(candidate.implementability_status || candidate.implementability || "unknown")} />
          <KeyValue label="Review Notes" value={String(candidate.review_notes || candidate.notes || "-")} />
          <KeyValue label="Universe Result" value={String(candidate.universe_backtest_status || candidate.classification_status || "not processed")} />
          <label className="space-y-2">
            <span className="form-label">Edit Candidate Fields</span>
            <textarea className="form-control min-h-64 resize-y font-mono text-xs leading-5" value={editJson} onChange={(event) => onEditJsonChange(event.target.value)} spellCheck={false} />
          </label>
          <label className="space-y-2">
            <span className="form-label">Review Note</span>
            <textarea className="form-control min-h-24 resize-y text-xs" value={note} onChange={(event) => onNoteChange(event.target.value)} />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <Action label="Approve" tone="green" disabled={busy} onClick={() => onReview("approve")} />
            <Action label="Reject" tone="red" disabled={busy} onClick={() => onReview("reject")} />
            <Action label="Duplicate" tone="amber" disabled={busy} onClick={() => onReview("mark_duplicate")} />
            <Action label="Process Approved" tone="green" disabled={busy} onClick={onProcess} />
          </div>
        </>
      ) : (
        <div className="border border-dashed border-line bg-ink p-4 text-sm text-muted">Select a candidate to inspect, edit, approve, reject, process, and view status.</div>
      )}
    </aside>
  );
}

function Warnings({
  duplicateWarnings,
  processingWarning,
  error,
  message,
}: {
  duplicateWarnings: string[];
  processingWarning: string | null;
  error: string | null;
  message: string | null;
}) {
  return (
    <div className="space-y-2">
      {duplicateWarnings.map((warning) => <div key={warning} className="border border-amber/60 bg-amber/10 p-3 text-xs text-amber">{warning}</div>)}
      {processingWarning ? <div className="border border-amber/60 bg-amber/10 p-3 text-xs leading-5 text-amber">{processingWarning}</div> : null}
      {message ? <div className="border border-green/60 bg-green/10 p-3 text-xs leading-5 text-green">{message}</div> : null}
      {error ? <div className="border border-red/60 bg-red/10 p-3 text-xs leading-5 text-red">{error}</div> : null}
    </div>
  );
}

function Action({ label, tone, disabled, onClick }: { label: string; tone: "green" | "red" | "amber"; disabled: boolean; onClick: () => void }) {
  const color = {
    green: "border-green text-green hover:bg-green/15",
    red: "border-red text-red hover:bg-red/15",
    amber: "border-amber text-amber hover:bg-amber/15",
  }[tone];
  return <button className={`border bg-transparent px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] disabled:border-line disabled:text-muted ${color}`} type="button" disabled={disabled} onClick={onClick}>{label}</button>;
}

function NumberInput({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="space-y-2">
      <span className="form-label">{label}</span>
      <input className="form-control font-mono" type="number" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-2">
      <span className="form-label">{label}</span>
      <input className="form-control font-mono" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-line bg-ink px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted">{label}</div>
      <div className="mt-1 break-all font-mono text-xs text-text">{value}</div>
    </div>
  );
}

function candidateId(candidate: StrategyCandidate, index: number): string {
  return String(candidate.candidate_id || candidate.id || candidate.strategy_id || candidate.slug || `candidate_${index + 1}`);
}

function duplicateRows(candidates: StrategyCandidate[]): string[] {
  return candidates
    .map((candidate, index) => {
      const warning = candidate.duplicate_warning || candidate.duplicate_status;
      return warning && String(warning).toLowerCase() !== "none" ? `${candidateId(candidate, index)}: ${String(warning)}` : "";
    })
    .filter(Boolean);
}

function parseEdits(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}
