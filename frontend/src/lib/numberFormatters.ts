export function formatCurrency(value: unknown, maximumFractionDigits = 0): string {
  const parsed = asNumber(value);
  if (parsed === null) return "-";
  return parsed.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits,
  });
}

export function formatPercent(value: unknown, maximumFractionDigits = 2): string {
  const parsed = asNumber(value);
  if (parsed === null) return "-";
  return `${parsed.toFixed(maximumFractionDigits)}%`;
}

export function formatScore(value: unknown): string {
  const parsed = asNumber(value);
  if (parsed === null) return "-";
  return parsed.toFixed(1);
}

export function formatNumber(value: unknown, maximumFractionDigits = 2): string {
  const parsed = asNumber(value);
  if (parsed === null) return "-";
  return parsed.toLocaleString(undefined, { maximumFractionDigits });
}

export function formatCompactNumber(value: unknown): string {
  const parsed = asNumber(value);
  if (parsed === null) return "-";
  return parsed.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 2 });
}

export function formatDate(value: unknown): string {
  if (!value) return "-";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
}

export function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}
