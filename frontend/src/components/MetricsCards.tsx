import type { MetricSet } from "../api/client";

type MetricsCardsProps = {
  metrics?: MetricSet;
};

const metricConfig: Array<{
  label: string;
  key: keyof MetricSet;
  format: (value: number | undefined) => string;
  tone?: (value: number | undefined) => string;
}> = [
  {
    label: "Total Return",
    key: "total_return_pct",
    format: formatPercent,
    tone: signedTone,
  },
  {
    label: "Sharpe",
    key: "sharpe_ratio",
    format: formatNumber,
  },
  {
    label: "Max Drawdown",
    key: "max_drawdown_pct",
    format: formatPercent,
    tone: () => "text-red",
  },
  {
    label: "Win Rate",
    key: "win_rate_pct",
    format: formatPercent,
  },
  {
    label: "Trades",
    key: "total_trades",
    format: (value) => `${value ?? 0}`,
  },
  {
    label: "Final Value",
    key: "final_value",
    format: formatCurrency,
    tone: signedTone,
  },
];

export default function MetricsCards({ metrics }: MetricsCardsProps) {
  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      {metricConfig.map((metric) => {
        const value = metrics?.[metric.key];
        return (
          <div key={metric.key} className="border border-line bg-panel px-4 py-3">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">{metric.label}</div>
            <div className={`text-xl font-semibold ${metric.tone?.(value) || "text-text"}`}>{metric.format(value)}</div>
          </div>
        );
      })}
    </section>
  );
}

function formatPercent(value: number | undefined): string {
  return typeof value === "number" ? `${value.toFixed(2)}%` : "0.00%";
}

function formatNumber(value: number | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "0.00";
}

function formatCurrency(value: number | undefined): string {
  return typeof value === "number"
    ? value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })
    : "$0";
}

function signedTone(value: number | undefined): string {
  if (typeof value !== "number") {
    return "text-text";
  }
  return value >= 0 ? "text-green" : "text-red";
}
