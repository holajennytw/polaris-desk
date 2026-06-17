// ============================================================
// lib/api.ts — 唯一資料存取層
// USE_MOCK=true → 讀 /mocks/xxx.json（public/ 靜態檔，模擬 400ms 延遲）
// USE_MOCK=false → 打 ${API_BASE}${path}
// ============================================================
import { USE_MOCK, API_BASE } from "./config";
import {
  normalizeAlerts, normalizeAsk, normalizeResearch, normalizeComparison, normalizeNews,
  normalizeLibrary, normalizeHistoryItem, normalizeNotifications,
  normalizeResolve, normalizeWatchItem, normalizeCompany,
} from "./adapters";

async function mockFetch(mock: string): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 400));
  const res = await fetch(`/mocks/${mock}.json`);
  if (!res.ok) throw new Error(`Mock fetch failed: ${mock}`);
  return res.json();
}

async function realFetch(path: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

const get = (mock: string, path: string) =>
  USE_MOCK ? mockFetch(mock) : realFetch(path);

const post = (mock: string, path: string, body: unknown) =>
  USE_MOCK ? mockFetch(mock) : realFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

// ── 各端點 ──

export const api = {
  async ask(query: string) {
    const raw = await post("ask", "/ask", { query }) as any;
    return normalizeAsk(raw);
  },

  async research(query: string) {
    const raw = await post("research", "/research", { question: query }) as any;
    return normalizeResearch(raw, query);
  },

  async alerts() {
    const raw = await get("alerts", "/alerts") as any[];
    return normalizeAlerts(raw);
  },

  async notifications() {
    const raw = await get("notifications", "/notifications") as any;
    return normalizeNotifications(raw);
  },

  async companies() {
    const raw = await get("companies", "/companies") as any[];
    return raw.map(normalizeCompany);
  },

  async company(id: string) {
    const mock = `company.${id}`;
    const raw = await (USE_MOCK ? mockFetch(mock) : realFetch(`/company/${id}`)) as any;
    return normalizeComparison(raw);
  },

  async resolve(query: string) {
    const raw = await post("resolve", "/resolve", { query }) as any;
    return normalizeResolve(raw);
  },

  async news() {
    const raw = await get("news", "/news") as any;
    return normalizeNews(raw);
  },

  async library() {
    const raw = await get("library", "/library") as any;
    return normalizeLibrary(raw);
  },

  async history() {
    const raw = await get("history", "/history") as any[];
    return raw.map(normalizeHistoryItem);
  },

  async watch() {
    const raw = await get("watch", "/watch") as any[];
    return raw.map(normalizeWatchItem);
  },

  async healthz() {
    const raw = await get("healthz", "/healthz") as any;
    return raw;
  },
};
