export type DashboardTab = "overview" | "backtest" | "monteCarlo" | "parameters" | "trades" | "diagnostics";

type DashboardTabsProps = {
  activeTab: DashboardTab;
  onChange: (tab: DashboardTab) => void;
};

const tabs: Array<{ id: DashboardTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "backtest", label: "Backtest" },
  { id: "monteCarlo", label: "Monte Carlo" },
  { id: "parameters", label: "Parameters" },
  { id: "trades", label: "Trades" },
  { id: "diagnostics", label: "Diagnostics" },
];

export default function DashboardTabs({ activeTab, onChange }: DashboardTabsProps) {
  return (
    <div className="flex overflow-x-auto border border-line bg-panel">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`min-w-32 border-r border-line px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] transition ${
            activeTab === tab.id ? "bg-panel2 text-cyan" : "text-muted hover:bg-panel2/50 hover:text-text"
          }`}
          type="button"
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
