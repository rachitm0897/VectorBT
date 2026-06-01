import { motion } from "framer-motion";
import type { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
};

export default function SectionCard({ title, subtitle, action, children, className = "", bodyClassName = "" }: SectionCardProps) {
  return (
    <motion.section
      className={`border border-line bg-panel shadow-[0_0_0_1px_rgba(255,255,255,0.015)] ${className}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="flex min-h-11 items-center justify-between gap-3 border-b border-line bg-panel2/60 px-4 py-2">
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text">{title}</h2>
          {subtitle ? <p className="mt-1 text-xs text-muted">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      <div className={bodyClassName || "p-4"}>{children}</div>
    </motion.section>
  );
}
