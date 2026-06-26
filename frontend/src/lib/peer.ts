// ============================================================
// lib/peer.ts — 前端同業比較工具函式
// buildComparison: 組合兩家公司的對比資料（mock 情境直接從 JSON 取）
// parseQuery: 解析自然語言查詢，抽出公司、季別、分頁
// ============================================================
import type { ComparisonVM } from "@/types/viewmodel";

// 公司辨識由 peer/page.tsx dynMatches 動態從 BQ company_dim.aliases 比對，不在此維護

// 季別 pattern
const PERIOD_PATTERN = /(\d{4})\s*[Q第]?\s*([1-4])/i;

// 分頁 keyword
const TAB_KEYWORDS: Record<string, string> = {
  "財務": "financial",
  "損益": "financial",
  "毛利": "financial",
  "營收": "financial",
  "EPS": "financial",
  "eps": "financial",
  "獲利": "financial",
  "法說": "calls",
  "call": "calls",
  "transcript": "calls",
  "逐字稿": "calls",
  "說法": "calls",
  "新聞": "news",
  "重大訊息": "news",
  "公告": "news",
  "估值": "valuation",
  "估值倍數": "valuation",
  "PE": "valuation",
  "本益比": "valuation",
  "PB": "valuation",
};

export interface ParsedQuery {
  ordered: Array<{ id: string; name: string; status: "ok" | "nodata" }>;
  period: string;
  year: number | null;
  tab: string;
}

export function parseQuery(q: string): ParsedQuery {
  // 季別：明確包含季度才填入；否則回空字串，由呼叫端沿用目前 fiscalPeriod
  let period = "";
  const pm = q.match(PERIOD_PATTERN);
  if (pm) period = `${pm[1]}Q${pm[2]}`;

  // 年份 only（如「2025年毛利率」）：提取年份供呼叫端推算最近季別
  let year: number | null = null;
  if (!period) {
    const ym = q.match(/(\d{4})年/);
    if (ym) year = parseInt(ym[1]);
  }

  // 分頁
  let tab = "financial";
  for (const [kw, t] of Object.entries(TAB_KEYWORDS)) {
    if (q.includes(kw)) { tab = t; break; }
  }

  return { ordered: [], period, year, tab };
}

// buildComparison: mock 情境下直接回傳已正規化的切片
// 真實情境由 api.company() 取得
export async function buildComparison(
  _aId: string,
  bId: string
): Promise<ComparisonVM | null> {
  try {
    const { api } = await import("./api");
    const data = await api.company(bId);
    return data;
  } catch {
    return null;
  }
}
