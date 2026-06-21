// ============================================================
// lib/api.ts — 唯一資料存取層
// USE_MOCK=true → 讀 /mocks/xxx.json（public/ 靜態檔，模擬 400ms 延遲）
// USE_MOCK=false → 打 ${API_BASE}${path}
// ============================================================
import { USE_MOCK, API_BASE } from "./config";
import {
  normalizeAlerts, normalizeAsk, normalizeResearch, normalizeComparison, normalizeNews,
  normalizeLibrary, normalizeNotifications,
  normalizeResolve, normalizeWatchItem, normalizeCompany,
} from "./adapters";
import { historyStore } from "./historyStore";
import { getSession } from "next-auth/react";
import type { ChunkRaw } from "@/types/api";
import type { DocContent } from "@/components/polaris/DocViewer";

// 有登入 → 回 Authorization header；無登入 / 斷網 → 空物件（後端視為匿名）
async function authHeaders(): Promise<Record<string, string>> {
  try {
    const session = await getSession();
    const t = (session as any)?.idToken as string | undefined;
    return t ? { Authorization: `Bearer ${t}` } : {};
  } catch {
    return {};
  }
}

async function mockFetch(mock: string): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 400));
  const res = await fetch(`/mocks/${mock}.json`);
  if (!res.ok) throw new Error(`Mock fetch failed: ${mock}`);
  return res.json();
}

async function realFetch(path: string, init?: RequestInit): Promise<unknown> {
  const auth = await authHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...auth, ...(init?.headers as Record<string, string> | undefined) },
  });
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
    return normalizeAsk(raw, query);
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
    if (USE_MOCK) {
      const raw = await get("news", "/news") as any;
      return normalizeNews(raw);
    }
    const raw = await realFetch("/events?type=news&limit=100") as any[];
    const items = raw.map(e => ({
      id: e.event_id as string,
      cite: e.ticker ?? "",
      title: e.title ?? "",
      summary: "",
      time: e.published_at ?? "",
      tags: e.ticker ? [e.ticker as string] : [],
      url: e.source_url ?? undefined,
    }));
    const tickerCounts: Record<string, number> = {};
    items.forEach(item => item.tags.forEach((t: string) => { tickerCounts[t] = (tickerCounts[t] ?? 0) + 1; }));
    const tabs = [
      { id: "all", label: "全部", count: items.length },
      ...Object.entries(tickerCounts).map(([ticker, count]) => ({ id: ticker, label: ticker, count })),
    ];
    return { updated: new Date().toLocaleDateString("zh-TW"), tabs, items };
  },

  async library() {
    const raw = await get("library", "/library") as any;
    return normalizeLibrary(raw);
  },

  async history() {
    try {
      const session = await getSession();
      if (session) {
        const raw = await realFetch("/history") as any[];
        return raw.map((h) => ({
          id: h.id as string,
          query: h.query as string,
          page: (h.origin ?? "research") as "research" | "peer",
          time: h.created_at
            ? new Date(h.created_at).toLocaleString("zh-TW", {
                timeZone: "Asia/Taipei", year: "numeric", month: "2-digit",
                day: "2-digit", hour: "2-digit", minute: "2-digit",
              })
            : "",
          tags: (h.tickers ?? []) as string[],
        }));
      }
    } catch {}
    return historyStore.read();
  },

  async historyOne(id: string): Promise<{ query: string; page: "research" | "peer"; result: unknown } | null> {
    try {
      const raw = await realFetch(`/history/${encodeURIComponent(id)}`) as any;
      return { query: raw.query, page: raw.origin ?? "research", result: raw.result };
    } catch {
      return null;
    }
  },

  async deleteHistory(id: string): Promise<void> {
    try {
      const session = await getSession();
      if (session) {
        await realFetch(`/history/${encodeURIComponent(id)}`, { method: "DELETE" });
      }
    } catch { /* 後端尚無 DELETE 端點時靜默，localStorage 仍執行 */ }
    historyStore.remove(id);
  },

  postHistory(origin: "research" | "peer", query: string, tickers: string[], result: unknown): void {
    if (USE_MOCK) return;
    authHeaders().then((auth) =>
      fetch(`${API_BASE}/history`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth },
        body: JSON.stringify({ origin, query, tickers, result }),
      })
    ).catch(() => {
      // 未登入 (401) 或網路錯誤時靜默忽略，localStorage 已有備援
    });
  },

  async watch() {
    const raw = await get("watch", "/watch") as any[];
    return raw.map(normalizeWatchItem);
  },

  async chunk(sourceId: string): Promise<DocContent | null> {
    if (USE_MOCK) return null;
    try {
      const raw = await realFetch(`/chunk/${encodeURIComponent(sourceId)}`) as ChunkRaw;
      return {
        key: raw.source_id,
        title: raw.title,
        kind: raw.kind_label,
        source_id: raw.source_id,
        page: raw.page ?? "頁碼未提供",
        period: raw.fiscal_period || undefined,
        trust: raw.trust,
        highlight: raw.highlight,
        hlTokens: raw.hl_tokens,
        body: raw.content.split(/(?<=。)|\n/).map((s) => s.trim()).filter(Boolean),
      };
    } catch {
      return null;
    }
  },

  async healthz() {
    const raw = await get("healthz", "/healthz") as any;
    return raw;
  },

  async markNotificationRead(id: string): Promise<void> {
    if (USE_MOCK) return;
    try {
      await realFetch(`/notifications/${encodeURIComponent(id)}/read`, { method: "POST" });
    } catch { /* best-effort，localStorage 已讀狀態仍保留 */ }
  },

  async getSubscriptions(): Promise<string[]> {
    try {
      const raw = await realFetch("/subscriptions") as { status: string; tickers: string[] };
      return raw.tickers ?? [];
    } catch {
      return [];
    }
  },

  async setSubscriptions(tickers: string[]): Promise<void> {
    await realFetch("/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers }),
    });
  },
};
