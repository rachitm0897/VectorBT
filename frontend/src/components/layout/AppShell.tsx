import type { ReactNode } from "react";

type AppShellProps = {
  sidebar: ReactNode;
  children: ReactNode;
};

export default function AppShell({ sidebar, children }: AppShellProps) {
  return (
    <main className="min-h-screen bg-ink text-text">
      <header className="sticky top-0 z-30 border-b border-line bg-ink/95 px-4 py-3 backdrop-blur lg:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-normal text-text">VectorBT Strategy Lab</h1>
            <p className="mt-0.5 text-xs uppercase tracking-[0.16em] text-muted">
              Deterministic research terminal / Finnhub daily candles
            </p>
          </div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-muted">
            <span className="border border-line bg-panel px-2 py-1">Backend API</span>
            <span className="border border-line bg-panel px-2 py-1">Dark Terminal</span>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[390px_minmax(0,1fr)] lg:p-5">
        {sidebar}
        <section className="min-w-0">{children}</section>
      </div>
    </main>
  );
}
