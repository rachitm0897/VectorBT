import { quantTheme } from "./chartThemes";

export function signedColor(value: unknown): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number) || number === 0) return quantTheme.neutral;
  return number > 0 ? quantTheme.positive : quantTheme.negative;
}

export function heatmapColor(value: number): string {
  if (!Number.isFinite(value) || value === 0) return "#253245";
  if (value > 0) return value > 8 ? "#1fa36b" : value > 3 ? "#247d63" : "#255c51";
  return value < -8 ? "#b84558" : value < -3 ? "#884052" : "#573444";
}

export function returnBucketColor(value: number): string {
  return value >= 0 ? quantTheme.positive : quantTheme.negative;
}
