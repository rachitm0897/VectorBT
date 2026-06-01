type TradesTableProps = {
  trades?: Array<Record<string, unknown>>;
};

const preferredColumns = [
  "entry_timestamp",
  "exit_timestamp",
  "size",
  "return",
  "pnl",
  "status",
  "direction",
];

export default function TradesTable({ trades = [] }: TradesTableProps) {
  const columns = resolveColumns(trades);

  return (
    <section className="panel-shell p-4">
      <div className="mb-3 flex items-center justify-between border-b border-line pb-3">
        <h2 className="section-title">Trades</h2>
        <span className="text-xs text-muted">{trades.length} rows</span>
      </div>

      {trades.length === 0 ? (
        <div className="border border-dashed border-line bg-ink px-4 py-8 text-center text-sm text-muted">
          No trades returned for this backtest.
        </div>
      ) : (
        <div className="max-h-80 overflow-auto border border-line">
          <table className="min-w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 bg-panel2 text-muted">
              <tr>
                {columns.map((column) => (
                  <th key={column} className="border-b border-line px-3 py-2 font-semibold uppercase tracking-[0.12em]">
                    {column.replaceAll("_", " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((trade, index) => (
                <tr key={index} className="odd:bg-ink/60 even:bg-panel hover:bg-panel2">
                  {columns.map((column) => (
                    <td key={column} className="whitespace-nowrap border-b border-line px-3 py-2 text-text">
                      {formatCell(column, trade[column])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function resolveColumns(trades: Array<Record<string, unknown>>): string[] {
  const available = new Set(trades.flatMap((trade) => Object.keys(trade)));
  const preferred = preferredColumns.filter((column) => available.has(column));
  const fallback = Array.from(available)
    .filter((column) => !preferred.includes(column))
    .slice(0, 4);
  return [...preferred, ...fallback];
}

function formatCell(column: string, value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    if (column === "return") {
      return `${(value * 100).toFixed(2)}%`;
    }
    if (column.includes("pnl") || column.includes("price")) {
      return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return String(value);
}
