import { memo, useMemo } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry, type ColDef } from "ag-grid-community";
import type { BacktestResult } from "../../api/client";
import { asNumber, formatCurrency, formatPercent } from "../../lib/numberFormatters";
import EmptyState from "../layout/EmptyState";
import SectionCard from "../layout/SectionCard";

ModuleRegistry.registerModules([AllCommunityModule]);

type TradesGridProps = {
  result: BacktestResult;
};

type TradeRow = {
  entry_date?: string;
  exit_date?: string;
  side?: string;
  entry_price?: number | null;
  exit_price?: number | null;
  return_pct?: number | null;
  pnl?: number | null;
  size?: number | null;
  duration?: string;
  status?: string;
};

function TradesGrid({ result }: TradesGridProps) {
  const rows = useMemo(() => normalizeTrades(result.tables?.trades || []), [result.tables?.trades]);
  const summary = useMemo(() => {
    const pnl = rows.reduce((sum, row) => sum + (row.pnl || 0), 0);
    const averageReturn = rows.length ? rows.reduce((sum, row) => sum + (row.return_pct || 0), 0) / rows.length : 0;
    return [{ entry_date: "Summary", exit_date: `${rows.length} trades`, return_pct: averageReturn, pnl }];
  }, [rows]);

  const columns = useMemo<ColDef<TradeRow>[]>(
    () => [
      { field: "entry_date", headerName: "Entry", filter: true, sortable: true, pinned: "left", minWidth: 115 },
      { field: "exit_date", headerName: "Exit", filter: true, sortable: true, minWidth: 115 },
      { field: "side", headerName: "Side", filter: true, sortable: true, width: 90 },
      { field: "size", headerName: "Size", sortable: true, width: 90, valueFormatter: (p) => formatNumberCell(p.value) },
      { field: "entry_price", headerName: "Entry Px", sortable: true, width: 110, valueFormatter: (p) => formatCurrency(p.value, 2) },
      { field: "exit_price", headerName: "Exit Px", sortable: true, width: 110, valueFormatter: (p) => formatCurrency(p.value, 2) },
      {
        field: "return_pct",
        headerName: "Return",
        sortable: true,
        width: 110,
        valueFormatter: (p) => formatPercent(p.value),
        cellClass: (p) => ((p.value || 0) >= 0 ? "text-green" : "text-red"),
      },
      { field: "pnl", headerName: "PnL", sortable: true, width: 110, valueFormatter: (p) => formatCurrency(p.value, 2) },
      { field: "duration", headerName: "Duration", sortable: true, width: 110 },
      { field: "status", headerName: "Status", filter: true, sortable: true, width: 110 },
    ],
    [],
  );

  return (
    <SectionCard title="Trades Blotter" subtitle="AG Grid Community / compact research table" bodyClassName="p-0">
      {rows.length ? (
        <div className="ag-theme-quartz-dark h-[520px] w-full">
          <AgGridReact
            rowData={rows}
            columnDefs={columns}
            pinnedBottomRowData={summary}
            rowHeight={30}
            headerHeight={34}
            suppressCellFocus
            animateRows={false}
            defaultColDef={{ resizable: true, filter: true }}
          />
        </div>
      ) : (
        <div className="p-4">
          <EmptyState title="No trades" message="This strategy did not return trades for the selected period." />
        </div>
      )}
    </SectionCard>
  );
}

function normalizeTrades(trades: Array<Record<string, unknown>>): TradeRow[] {
  return trades.map((trade) => {
    const rawReturn = asNumber(trade.return) ?? asNumber(trade.return_pct);
    return {
      entry_date: stringValue(trade.entry_timestamp ?? trade.entry_date ?? trade.entry_time),
      exit_date: stringValue(trade.exit_timestamp ?? trade.exit_date ?? trade.exit_time),
      side: stringValue(trade.direction ?? trade.side ?? "Long"),
      entry_price: asNumber(trade.entry_price ?? trade.avg_entry_price),
      exit_price: asNumber(trade.exit_price ?? trade.avg_exit_price),
      return_pct: rawReturn === null ? null : Math.abs(rawReturn) <= 1 ? rawReturn * 100 : rawReturn,
      pnl: asNumber(trade.pnl ?? trade.profit),
      size: asNumber(trade.size),
      duration: stringValue(trade.duration),
      status: stringValue(trade.status),
    };
  });
}

function stringValue(value: unknown): string | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  return String(value);
}

function formatNumberCell(value: unknown): string {
  const parsed = asNumber(value);
  return parsed === null ? "-" : parsed.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export default memo(TradesGrid);
