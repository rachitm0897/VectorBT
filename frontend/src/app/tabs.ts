export type PrimaryTab = "chat" | "manual" | "discovery" | "system";

export const primaryTabs: Array<{ id: PrimaryTab; label: string }> = [
  { id: "chat", label: "AI Research Chat" },
  { id: "manual", label: "Manual Research Lab" },
  { id: "discovery", label: "Strategy Discovery Lab" },
  { id: "system", label: "System / Health / Settings" },
];
