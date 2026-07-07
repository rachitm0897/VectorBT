import { useEffect, useState } from "react";
import { getResearchRun, listResearchRuns, type ResearchResultEnvelope, type ResearchRunSummary } from "../../api/client";
import A2UITemplateRenderer from "../../components/A2UITemplateRenderer";

export default function RunInspector() {
  const [runs, setRuns] = useState<ResearchRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<ResearchResultEnvelope | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      const response = await listResearchRuns(25);
      setRuns(response.runs);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not load research runs.");
    } finally {
      setBusy(false);
    }
  }

  async function loadRun(runId: string) {
    setBusy(true);
    setError(null);
    try {
      const response = await getResearchRun(runId);
      setSelectedRun(response.run || null);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not load research run.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="panel-shell p-4">
      <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
        <h3 className="section-title">Recent Runs</h3>
        <button className="terminal-button" type="button" disabled={busy} onClick={() => void refresh()}>
          Refresh Runs
        </button>
      </div>
      {error ? <div className="mb-3 border border-red/60 bg-red/10 p-3 text-xs text-red">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
        <div className="max-h-96 overflow-auto border border-line">
          <table className="min-w-full border-collapse font-mono text-xs">
            <thead className="bg-panel2 text-muted">
              <tr>
                <th className="border-b border-line px-3 py-2 text-left">Run ID</th>
                <th className="border-b border-line px-3 py-2 text-left">Workflow</th>
                <th className="border-b border-line px-3 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id} className="cursor-pointer odd:bg-ink even:bg-panel" onClick={() => run.run_id && void loadRun(run.run_id)}>
                  <td className="border-b border-line px-3 py-2 text-green">{run.run_id}</td>
                  <td className="border-b border-line px-3 py-2 text-muted">{run.workflow_type || "-"}</td>
                  <td className="border-b border-line px-3 py-2 text-muted">{run.status || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!runs.length ? <div className="p-4 text-xs text-muted">No persisted runs returned.</div> : null}
        </div>
        <div className="min-w-0">
          {selectedRun ? <A2UITemplateRenderer envelope={selectedRun} /> : <div className="border border-dashed border-line bg-ink p-4 text-sm text-muted">Select a run to reload its persisted settings, metrics, weights, artifacts, warnings, and errors.</div>}
        </div>
      </div>
    </section>
  );
}
