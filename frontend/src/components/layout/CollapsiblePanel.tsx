import { useState, type ReactNode } from "react";

type CollapsiblePanelProps = {
  title: string;
  defaultOpen?: boolean;
  summary?: ReactNode;
  rightAction?: ReactNode;
  children: ReactNode;
};

export default function CollapsiblePanel({
  title,
  defaultOpen = false,
  summary,
  rightAction,
  children,
}: CollapsiblePanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section className="panel-shell">
      <div className="flex items-center gap-3 px-4 py-3">
        <button
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
          type="button"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((current) => !current)}
        >
          <span className="flex h-6 w-6 shrink-0 items-center justify-center border border-line bg-ink font-mono text-xs text-muted">
            {isOpen ? "-" : "+"}
          </span>
          <span className="min-w-0">
            <span className="section-title block">{title}</span>
            {summary ? <span className="mt-1 block truncate text-xs text-muted">{summary}</span> : null}
          </span>
        </button>

        {rightAction ? <div className="shrink-0">{rightAction}</div> : null}
      </div>

      <div className={isOpen ? "border-t border-line p-4" : "hidden"}>{children}</div>
    </section>
  );
}
