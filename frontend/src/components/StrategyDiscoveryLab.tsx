import { useState } from "react";
import {
  discoverStrategyCandidates,
  processApprovedStrategy,
  reviewStrategyCandidate,
  type StrategyCandidate,
} from "../api/client";

type StrategyDiscoveryLabProps = {
  isLoading: boolean;
};

const sourceOptions = ["openalex", "crossref", "arxiv"];

export default function StrategyDiscoveryLab({ isLoading }: StrategyDiscoveryLabProps) {
  const [query, setQuery] = useState("equity momentum reversal risk adjusted strategy");
  const [sources, setSources] = useState<string[]>(["openalex", "crossref", "arxiv"]);
  const [maxCandidates, setMaxCandidates] = useState(10);
  const [candidates, setCandidates] = useState<StrategyCandidate[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSearch() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await discoverStrategyCandidates({
        query,
        sources,
        max_results_per_source: 5,
        max_candidates: maxCandidates,
      });
      setCandidates(response.candidates || []);
      setMessage(`Loaded ${response.count ?? response.candidates?.length ?? 0} candidates.`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Discovery failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReview(action: "approve" | "reject" | "mark_duplicate" | "request_changes") {
    if (!selectedCandidateId.trim()) {
      setError("Select or enter a candidate ID before review.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await reviewStrategyCandidate(selectedCandidateId.trim(), {
        action,
        reviewer: "frontend",
        reviewer_note: note,
        edits: {},
      });
      setMessage(`Candidate ${action.replace("_", " ")} recorded.`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Candidate review failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleProcess() {
    if (!selectedCandidateId.trim()) {
      setError("Select or enter an approved candidate ID before processing.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await processApprovedStrategy(selectedCandidateId.trim());
      setMessage(String(response.message || "Approved candidate processed."));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Approved candidate processing failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-shell p-4">
      <div className="mb-3 flex items-center justify-between border-b border-line pb-3">
        <h2 className="section-title">Strategy Discovery Lab</h2>
        <span className="border border-line px-2 py-1 font-mono text-[11px] text-muted">
          {candidates.length} candidates
        </span>
      </div>

      <div className="space-y-4">
        <label className="space-y-2">
          <span className="form-label">Literature Query</span>
          <textarea
            className="form-control min-h-24 resize-y text-sm leading-6"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>

        <div className="grid grid-cols-3 gap-2">
          {sourceOptions.map((source) => (
            <label key={source} className="flex items-center gap-2 border border-line bg-ink px-3 py-2 text-xs text-muted">
              <input
                type="checkbox"
                checked={sources.includes(source)}
                onChange={(event) => {
                  setSources((current) =>
                    event.target.checked ? [...current, source] : current.filter((item) => item !== source),
                  );
                }}
              />
              <span className="font-mono">{source}</span>
            </label>
          ))}
        </div>

        <label className="space-y-2">
          <span className="form-label">Max Candidates</span>
          <input
            className="form-control"
            type="number"
            min={1}
            max={50}
            value={maxCandidates}
            onChange={(event) => setMaxCandidates(Number(event.target.value))}
          />
        </label>

        <button
          className="w-full border border-amber bg-amber/15 px-4 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber transition hover:bg-amber/25 disabled:cursor-not-allowed disabled:border-line disabled:bg-line/30 disabled:text-muted"
          type="button"
          disabled={isLoading || busy || !query.trim() || sources.length === 0}
          onClick={() => void handleSearch()}
        >
          {busy ? "Running Discovery" : "Discover Candidates"}
        </button>

        <CandidateList candidates={candidates} selectedId={selectedCandidateId} onSelect={setSelectedCandidateId} />

        <div className="space-y-3 border border-line bg-ink p-3">
          <label className="space-y-2">
            <span className="form-label">Candidate ID</span>
            <input
              className="form-control font-mono"
              value={selectedCandidateId}
              onChange={(event) => setSelectedCandidateId(event.target.value)}
            />
          </label>
          <label className="space-y-2">
            <span className="form-label">Review Note</span>
            <textarea className="form-control min-h-20 resize-y text-xs" value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <ActionButton label="Approve" onClick={() => void handleReview("approve")} disabled={busy} tone="green" />
            <ActionButton label="Reject" onClick={() => void handleReview("reject")} disabled={busy} tone="red" />
            <ActionButton label="Duplicate" onClick={() => void handleReview("mark_duplicate")} disabled={busy} tone="amber" />
            <ActionButton label="Process" onClick={() => void handleProcess()} disabled={busy} tone="green" />
          </div>
        </div>

        {message ? <div className="border border-green/50 bg-green/10 p-3 text-xs leading-5 text-green">{message}</div> : null}
        {error ? <div className="border border-red/60 bg-red/10 p-3 text-xs leading-5 text-red">{error}</div> : null}
      </div>
    </section>
  );
}

function CandidateList({
  candidates,
  selectedId,
  onSelect,
}: {
  candidates: StrategyCandidate[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  if (!candidates.length) {
    return <div className="border border-dashed border-line bg-ink p-3 text-xs leading-5 text-muted">No candidates loaded.</div>;
  }
  return (
    <div className="max-h-96 space-y-2 overflow-auto">
      {candidates.map((candidate, index) => {
        const id = candidateId(candidate, index);
        const title = String(candidate.title || candidate.name || candidate.strategy_name || id);
        return (
          <button
            key={id}
            className={`block w-full border px-3 py-2 text-left text-xs leading-5 ${
              selectedId === id ? "border-green bg-green/10 text-text" : "border-line bg-ink text-muted hover:border-amber"
            }`}
            type="button"
            onClick={() => onSelect(id)}
          >
            <span className="mb-1 block font-mono text-text">{id}</span>
            <span className="block font-semibold text-amber">{title}</span>
            <span className="line-clamp-3">{String(candidate.abstract || candidate.description || candidate.summary || "")}</span>
          </button>
        );
      })}
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  tone,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
  tone: "green" | "red" | "amber";
}) {
  const color = {
    green: "border-green text-green hover:bg-green/15",
    red: "border-red text-red hover:bg-red/15",
    amber: "border-amber text-amber hover:bg-amber/15",
  }[tone];
  return (
    <button
      className={`border bg-transparent px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] disabled:cursor-not-allowed disabled:border-line disabled:text-muted ${color}`}
      type="button"
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function candidateId(candidate: StrategyCandidate, index: number): string {
  return String(
    candidate.candidate_id ||
      candidate.id ||
      candidate.strategy_id ||
      candidate.slug ||
      `candidate_${index + 1}`,
  );
}
