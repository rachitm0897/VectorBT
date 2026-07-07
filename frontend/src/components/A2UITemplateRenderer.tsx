import { useEffect, useMemo, useState } from "react";
import { A2uiSurface, basicCatalog } from "@a2ui/react/v0_9";
import { injectStyles } from "@a2ui/react/styles";
import { MessageProcessor } from "@a2ui/web_core/v0_9";
import type { ResearchResultEnvelope, UITemplateSpec } from "../api/client";
import SectionCard from "./layout/SectionCard";

type A2UITemplateRendererProps = {
  envelope: ResearchResultEnvelope | null;
};

type Point = Record<string, unknown>;

const allowedTemplates = new Set([
  "single_stock_research",
  "optimized_multi_stock_portfolio",
  "strategy_comparison",
  "strategy_catalogue_details",
  "monte_carlo_deep_dive",
  "discovery_candidate_review",
  "universe_backtest_classification",
  "error_data_quality_report",
]);

export default function A2UITemplateRenderer({ envelope }: A2UITemplateRendererProps) {
  if (!envelope) {
    return null;
  }

  const spec = normalizeSpec(envelope);
  const props = spec.props || {};
  const templateId = allowedTemplates.has(spec.template_id) ? spec.template_id : "error_data_quality_report";
  const metrics = objectValue(props.metrics) || envelope.metrics || {};
  const summary = objectValue(props.summary) || envelope.summary || {};
  const allocations = objectValue(props.allocations) || envelope.allocations || {};
  const equity = arrayValue(props.equity) || envelope.equity || [];
  const drawdown = arrayValue(props.drawdown) || envelope.drawdown || [];
  const trades = arrayValue(props.trades) || envelope.trades || [];
  const frontier = arrayValue(props.frontier) || envelope.frontier || [];
  const monteCarlo = objectValue(props.monte_carlo) || envelope.monte_carlo || {};

  return (
    <div className="space-y-4">
      <A2UISummarySurface
        spec={spec}
        status={envelope.status}
        runId={envelope.run_id || stringValue(props.run_id)}
        workflowType={envelope.workflow_type || stringValue(props.workflow_type) || undefined}
      />

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <SectionCard title={templateTitle(templateId)} subtitle={envelope.strategy_version || templateId}>
          <div className="space-y-4">
            <MetricGrid metrics={{ ...summary, ...metrics }} />
            <LinePanel title="Equity" points={equity} valueKeys={["value", "equity", "portfolio_value"]} />
            <LinePanel title="Drawdown" points={drawdown} valueKeys={["drawdown", "drawdown_pct", "value"]} />
            <MonteCarloPanel monteCarlo={monteCarlo} />
          </div>
        </SectionCard>

        <div className="space-y-4">
          <SectionCard title="Strategy" subtitle={strategyName(envelope)}>
            <KeyValueBlock
              data={{
                run_id: envelope.run_id || "-",
                status: envelope.status,
                workflow: envelope.workflow_type || "-",
                universe: summarizeUniverse(envelope.universe),
                persistence: envelope.persistence?.status || envelope.persistence?.enabled || "-",
              }}
            />
          </SectionCard>

          <SectionCard title="Allocations" subtitle="weights">
            <WeightsList allocations={allocations} />
          </SectionCard>

          <SectionCard title="Artifacts" subtitle={`${(envelope.artifacts || spec.artifacts || []).length} refs`}>
            <ArtifactList artifacts={envelope.artifacts || spec.artifacts || []} />
          </SectionCard>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <SectionCard title="Frontier" subtitle={`${frontier.length} points`}>
          <LinePanel points={frontier} valueKeys={["sharpe_ratio", "return", "expected_return"]} compact />
        </SectionCard>
        <SectionCard title="Trades" subtitle={`${trades.length} rows`}>
          <CompactTable rows={trades} />
        </SectionCard>
      </div>

      <Warnings warnings={envelope.warnings || spec.warnings || []} errors={envelope.errors || []} />
    </div>
  );
}

function A2UISummarySurface({
  spec,
  status,
  runId,
  workflowType,
}: {
  spec: UITemplateSpec;
  status?: string;
  runId?: string | null;
  workflowType?: string;
}) {
  const messages = useMemo(
    () => [
      {
        version: "v0.9" as const,
        createSurface: { surfaceId: "research-summary", catalogId: basicCatalog.id },
      },
      {
        version: "v0.9" as const,
        updateComponents: {
          surfaceId: "research-summary",
          components: [
            { id: "root", component: "Column", children: ["title", "body"] },
            { id: "title", component: "Text", text: { path: "/title" } },
            { id: "body", component: "Text", text: { path: "/body" } },
          ],
        },
      },
      {
        version: "v0.9" as const,
        updateDataModel: {
          surfaceId: "research-summary",
          path: "/",
          value: {
            title: spec.title || templateTitle(spec.template_id),
            body: `${status || "unknown"} / ${workflowType || spec.template_id} / ${runId || "no run id"}`,
          },
        },
      },
    ],
    [runId, spec.template_id, spec.title, status, workflowType],
  );

  const processor = useMemo(() => {
    const next = new MessageProcessor([basicCatalog]);
    next.processMessages(messages);
    return next;
  }, [messages]);
  const [surfaces, setSurfaces] = useState(() => Array.from(processor.model.surfacesMap.values()));

  useEffect(() => {
    injectStyles();
    setSurfaces(Array.from(processor.model.surfacesMap.values()));
    const created = processor.onSurfaceCreated(() => setSurfaces(Array.from(processor.model.surfacesMap.values())));
    const deleted = processor.onSurfaceDeleted(() => setSurfaces(Array.from(processor.model.surfacesMap.values())));
    return () => {
      created.unsubscribe();
      deleted.unsubscribe();
    };
  }, [processor]);

  return (
    <div className="panel-shell a2ui-terminal-surface p-3 font-mono text-xs">
      {surfaces.map((surface) => (
        <A2uiSurface key={surface.id} surface={surface} />
      ))}
    </div>
  );
}

function MetricGrid({ metrics }: { metrics: Record<string, unknown> }) {
  const rows = Object.entries(metrics).filter(([, value]) => value !== null && value !== undefined).slice(0, 12);
  if (!rows.length) {
    return <div className="border border-line bg-ink p-3 text-xs text-muted">No compact metrics returned.</div>;
  }
  return (
    <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
      {rows.map(([key, value]) => (
        <div key={key} className="border border-line bg-ink p-3">
          <div className="truncate text-[10px] uppercase tracking-[0.12em] text-muted">{labelize(key)}</div>
          <div className="mt-1 truncate font-mono text-sm text-text">{formatValue(value)}</div>
        </div>
      ))}
    </div>
  );
}

function LinePanel({
  title,
  points,
  valueKeys,
  compact,
}: {
  title?: string;
  points: Point[];
  valueKeys: string[];
  compact?: boolean;
}) {
  const series = points
    .map((point, index) => ({ index, value: numericValue(point, valueKeys) }))
    .filter((point) => Number.isFinite(point.value));
  if (!series.length) {
    return <div className="border border-line bg-ink p-3 text-xs text-muted">{title || "Series"} unavailable.</div>;
  }
  const values = series.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 100;
  const height = compact ? 54 : 110;
  const path = series
    .map((point, idx) => {
      const x = series.length === 1 ? 0 : (idx / (series.length - 1)) * width;
      const y = height - ((point.value - min) / span) * height;
      return `${idx === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <div className="border border-line bg-ink p-3">
      {title ? <div className="mb-2 text-[10px] uppercase tracking-[0.12em] text-muted">{title}</div> : null}
      <svg className="h-28 w-full overflow-visible" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <path d={path} fill="none" stroke="#2dd47f" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-2 flex justify-between font-mono text-[10px] text-muted">
        <span>{formatValue(min)}</span>
        <span>{formatValue(max)}</span>
      </div>
    </div>
  );
}

function MonteCarloPanel({ monteCarlo }: { monteCarlo: Record<string, unknown> }) {
  const paths = objectValue(monteCarlo.percentile_paths) || {};
  const p5 = numberArray(paths.p5);
  const p50 = numberArray(paths.p50);
  const p95 = numberArray(paths.p95);
  if (!p50.length) {
    return <div className="border border-line bg-ink p-3 text-xs text-muted">Monte Carlo fan unavailable.</div>;
  }
  return (
    <div className="border border-line bg-ink p-3">
      <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.12em] text-muted">
        <span>Monte Carlo</span>
        <span>{String(monteCarlo.mode || monteCarlo.method || "returns")}</span>
      </div>
      <FanChart p5={p5} p50={p50} p95={p95} />
    </div>
  );
}

function FanChart({ p5, p50, p95 }: { p5: number[]; p50: number[]; p95: number[] }) {
  const all = [...p5, ...p50, ...p95].filter(Number.isFinite);
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const width = 100;
  const height = 110;
  const toPath = (series: number[]) =>
    series
      .map((value, index) => {
        const x = series.length === 1 ? 0 : (index / (series.length - 1)) * width;
        const y = height - ((value - min) / span) * height;
        return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");
  return (
    <svg className="h-28 w-full overflow-visible" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <path d={toPath(p95)} fill="none" stroke="#91a0b6" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d={toPath(p50)} fill="none" stroke="#2dd47f" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      <path d={toPath(p5)} fill="none" stroke="#ff5c7a" strokeWidth="1" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function WeightsList({ allocations }: { allocations: Record<string, unknown> }) {
  const weights = objectValue(allocations.weights) || allocations;
  const rows = Object.entries(weights)
    .filter(([, value]) => typeof value === "number")
    .sort((a, b) => Number(b[1]) - Number(a[1]));
  if (!rows.length) {
    return <div className="border border-line bg-ink p-3 text-xs text-muted">No portfolio weights returned.</div>;
  }
  return (
    <div className="space-y-2">
      {rows.slice(0, 20).map(([symbol, value]) => (
        <div key={symbol} className="grid grid-cols-[70px_minmax(0,1fr)_68px] items-center gap-2 font-mono text-xs">
          <span className="text-text">{symbol}</span>
          <span className="h-2 border border-line bg-ink">
            <span
              className="block h-full bg-green"
              style={{ width: `${Math.min(100, Math.max(0, Math.abs(Number(value)) * 100))}%` }}
            />
          </span>
          <span className="text-right text-muted">{(Number(value) * 100).toFixed(2)}%</span>
        </div>
      ))}
    </div>
  );
}

function CompactTable({ rows }: { rows: Point[] }) {
  if (!rows.length) {
    return <div className="border border-line bg-ink p-3 text-xs text-muted">No rows returned.</div>;
  }
  const columns = Array.from(new Set(rows.slice(0, 20).flatMap((row) => Object.keys(row)))).slice(0, 6);
  return (
    <div className="overflow-auto border border-line">
      <table className="min-w-full border-collapse font-mono text-xs">
        <thead className="bg-panel2 text-muted">
          <tr>
            {columns.map((column) => (
              <th key={column} className="border-b border-line px-3 py-2 text-left font-semibold uppercase">
                {labelize(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 20).map((row, index) => (
            <tr key={index} className="odd:bg-ink even:bg-panel">
              {columns.map((column) => (
                <td key={column} className="border-b border-line px-3 py-2 text-muted">
                  {formatValue(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArtifactList({ artifacts }: { artifacts: Array<Record<string, unknown>> }) {
  if (!artifacts.length) {
    return <div className="border border-line bg-ink p-3 text-xs text-muted">No artifact references.</div>;
  }
  return (
    <div className="space-y-2">
      {artifacts.map((artifact, index) => {
        const url = stringValue(artifact.artifact_url);
        return url ? (
          <a
            key={`${url}-${index}`}
            className="block break-all border border-line bg-ink px-3 py-2 font-mono text-xs text-green hover:border-green"
            href={url}
            target="_blank"
            rel="noreferrer"
          >
            {url}
          </a>
        ) : (
          <div key={index} className="break-all border border-line bg-ink px-3 py-2 font-mono text-xs text-muted">
            {formatValue(artifact.artifact_id || artifact.artifact_path || artifact.artifact_type || "artifact")}
          </div>
        );
      })}
    </div>
  );
}

function KeyValueBlock({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-3 border border-line bg-ink px-3 py-2">
          <span className="text-[10px] uppercase tracking-[0.12em] text-muted">{labelize(key)}</span>
          <span className="break-all text-right font-mono text-xs text-text">{formatValue(value)}</span>
        </div>
      ))}
    </div>
  );
}

function Warnings({ warnings, errors }: { warnings: string[]; errors: string[] }) {
  if (!warnings.length && !errors.length) {
    return null;
  }
  return (
    <div className="space-y-2">
      {errors.map((error) => (
        <div key={error} className="border border-red/60 bg-red/10 px-3 py-2 text-sm text-red">
          {error}
        </div>
      ))}
      {warnings.map((warning) => (
        <div key={warning} className="border border-amber/60 bg-amber/10 px-3 py-2 text-sm text-amber">
          {warning}
        </div>
      ))}
    </div>
  );
}

function normalizeSpec(envelope: ResearchResultEnvelope): UITemplateSpec {
  const raw = objectValue(envelope.ui_spec) || {};
  const templateId = stringValue(raw.template_id) || envelope.ui_hint || envelope.workflow_type || "strategy_catalogue_details";
  return {
    template_id: templateId,
    title: stringValue(raw.title),
    props: objectValue(raw.props) || {},
    artifacts: arrayValue(raw.artifacts) || envelope.artifacts || [],
    warnings: Array.isArray(raw.warnings) ? raw.warnings.map(String) : envelope.warnings || [],
  };
}

function templateTitle(templateId: string) {
  return templateId
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function strategyName(envelope: ResearchResultEnvelope): string {
  const strategy = objectValue(envelope.strategy);
  return stringValue(strategy?.name) || stringValue(strategy?.strategy_id) || "-";
}

function summarizeUniverse(universe: Record<string, unknown> | undefined): string {
  const symbols = Array.isArray(universe?.symbols) ? universe.symbols.map(String) : [];
  if (symbols.length) return symbols.join(", ");
  return formatValue(universe || "-");
}

function labelize(value: string): string {
  return value.replace(/_/g, " ");
}

function formatValue(value: unknown): string {
  if (typeof value === "number") {
    if (Math.abs(value) < 1 && value !== 0) return value.toFixed(4);
    if (Math.abs(value) > 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return value.toFixed(2);
  }
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value === null || value === undefined) return "-";
  return JSON.stringify(value);
}

function numericValue(point: Point, keys: string[]): number {
  for (const key of keys) {
    const value = point[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  }
  return Number.NaN;
}

function numberArray(value: unknown): number[] {
  return Array.isArray(value) ? value.map(Number).filter(Number.isFinite) : [];
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function arrayValue(value: unknown): Point[] | null {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === "object") as Point[]) : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}
