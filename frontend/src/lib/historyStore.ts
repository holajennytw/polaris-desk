const LS_KEY = "polaris_history";
const MAX_ENTRIES = 100;

export interface HistoryEntry {
  id: string;
  query: string;
  page: "research" | "peer";
  time: string;
  tags: string[];
}

function now(): string {
  return new Date().toLocaleString("zh-TW", {
    timeZone: "Asia/Taipei",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export const historyStore = {
  read(): HistoryEntry[] {
    if (typeof window === "undefined") return [];
    try {
      return JSON.parse(localStorage.getItem(LS_KEY) ?? "[]");
    } catch {
      return [];
    }
  },

  write(entry: Omit<HistoryEntry, "id" | "time">): void {
    const item: HistoryEntry = {
      ...entry,
      id: `hist-${Date.now()}`,
      time: now(),
    };
    const existing = historyStore.read();
    localStorage.setItem(LS_KEY, JSON.stringify([item, ...existing].slice(0, MAX_ENTRIES)));
  },
};

export function extractTickers(text: string): string[] {
  return [...new Set(text.match(/\b\d{4}\b/g) ?? [])];
}
