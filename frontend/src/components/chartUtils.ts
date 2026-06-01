export const chartGrid = "#1f2b3b";
export const axisColor = "#91a0b6";
export const tooltipStyle = {
  backgroundColor: "#0d131c",
  border: "1px solid #243244",
  color: "#e8eef7",
};

export function compactCurrency(value: unknown): string {
  if (typeof value !== "number") {
    return "";
  }
  return value.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 2,
  });
}

export function compactNumber(value: unknown): string {
  return typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "";
}
