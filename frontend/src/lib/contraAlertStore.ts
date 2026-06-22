import type { AlertVM } from "@/types/viewmodel";

// Client-side store for contradiction alerts, scoped per page.
// Each page gets its own sessionStorage key so research / peer alerts don't bleed across.
// R3 dependency: once GET /alerts returns an `origin` field, server-side alerts can also
// be filtered per page; until then, useAlerts() returns all watchdog alerts globally.

export type ContraAlert = AlertVM & { origin: "contradiction"; cite_key?: string };
export type ContraPage = "research" | "peer";

const KEYS: Record<ContraPage, string> = {
  research: "polaris_contra_alerts_research",
  peer:     "polaris_contra_alerts_peer",
};

type Listener = (alerts: ContraAlert[]) => void;
const listeners: Record<ContraPage, Set<Listener>> = {
  research: new Set(),
  peer:     new Set(),
};

function read(page: ContraPage): ContraAlert[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(sessionStorage.getItem(KEYS[page]) ?? "[]"); } catch { return []; }
}

function write(alerts: ContraAlert[], page: ContraPage) {
  if (typeof window === "undefined") return;
  try { sessionStorage.setItem(KEYS[page], JSON.stringify(alerts)); } catch {}
  listeners[page].forEach(l => l(alerts));
}

export const contraAlertStore = {
  get:   (page: ContraPage) => read(page),
  set:   (alerts: ContraAlert[], page: ContraPage) => write(alerts, page),
  clear: (page: ContraPage) => write([], page),
  subscribe: (fn: Listener, page: ContraPage) => {
    listeners[page].add(fn);
    return () => { listeners[page].delete(fn); };
  },
};
