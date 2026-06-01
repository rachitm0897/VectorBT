import type { ReactNode } from "react";

type SidebarProps = {
  children: ReactNode;
};

export default function Sidebar({ children }: SidebarProps) {
  return <aside className="space-y-4 lg:sticky lg:top-[76px] lg:max-h-[calc(100vh-96px)] lg:overflow-auto">{children}</aside>;
}
