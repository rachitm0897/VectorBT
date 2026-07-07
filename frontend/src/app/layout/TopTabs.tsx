import { primaryTabs, type PrimaryTab } from "../tabs";

type TopTabsProps = {
  activeTab: PrimaryTab;
  onChange: (tab: PrimaryTab) => void;
};

export default function TopTabs({ activeTab, onChange }: TopTabsProps) {
  return (
    <nav className="flex min-w-0 flex-wrap gap-1 border-b border-line bg-ink px-3 pt-3">
      {primaryTabs.map((tab) => (
        <button
          key={tab.id}
          className={`border border-b-0 px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${
            activeTab === tab.id
              ? "border-green bg-panel text-green"
              : "border-line bg-ink text-muted hover:border-muted hover:text-text"
          }`}
          type="button"
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
