// ============================================================
// lib/peer.ts — 前端同業比較工具函式
// buildComparison: 組合兩家公司的對比資料（mock 情境直接從 JSON 取）
// parseQuery: 解析自然語言查詢，抽出公司、季別、分頁
// ============================================================
import type { ComparisonVM } from "@/types/viewmodel";

// 公司辨識由 peer/page.tsx dynMatches 動態從 BQ company_dim.aliases 比對，不在此維護

// 季別 pattern
const PERIOD_PATTERN = /(\d{4})\s*[Q第]?\s*([1-4])/i;

// 年份 only（無明確季度）：須帶「年 / 全年 / 年度」後綴才算年份，避免把 4 位
// 股號（如 2330）誤判成年份。「2025全年」「2025年度」「2025年」皆涵蓋。
const YEAR_PATTERN = /(\d{4})\s*(?:全年度|全年|年度|年)/;

// 指名指標 → canonical metric_id（供呼叫端在該指標於選定期別無資料時提示，
// 而非靜默退回月營收）。順序重要：較長/較專指的關鍵字排前面。
const METRIC_KEYWORDS: Array<[string, string]> = [
  ["每股盈餘", "eps"],
  ["EPS", "eps"],
  ["eps", "eps"],
  ["毛利率", "gross_margin"],
  ["毛利", "gross_margin"],
  ["淨利率", "net_margin"],
  ["營業利益率", "operating_margin"],
  ["營業利益", "operating_income"],
  ["營收年增", "revenue_yoy"],
  ["ROE", "roe"],
  ["roe", "roe"],
  ["ROA", "roa"],
  ["roa", "roa"],
  ["本益比", "pe_ratio"],
  ["PE", "pe_ratio"],
];

// 各 metric_id 的中文顯示名（提示訊息用）
const METRIC_LABELS: Record<string, string> = {
  eps: "EPS",
  gross_margin: "毛利率",
  net_margin: "淨利率",
  operating_margin: "營業利益率",
  operating_income: "營業利益",
  revenue_yoy: "營收年增率",
  roe: "ROE",
  roa: "ROA",
  pe_ratio: "本益比",
};

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
  /** 使用者指名的指標 metric_id（如「EPS」→"eps"），未指名為 null */
  metric: string | null;
  /** metric 的中文顯示名，供提示訊息使用 */
  metricLabel: string | null;
}

export function parseQuery(q: string): ParsedQuery {
  // 季別：明確包含季度才填入；否則回空字串，由呼叫端沿用目前 fiscalPeriod
  let period = "";
  const pm = q.match(PERIOD_PATTERN);
  if (pm) period = `${pm[1]}Q${pm[2]}`;

  // 年份 only（如「2025全年 EPS」「2025年毛利率」）：提取年份供呼叫端推算最近季別。
  // 「全年」語意上 = 年度（Q4 累計），呼叫端的 year fallback 會取該年最新一季（通常 Q4）。
  let year: number | null = null;
  if (!period) {
    const ym = q.match(YEAR_PATTERN);
    if (ym) year = parseInt(ym[1]);
  }

  // 指名指標
  let metric: string | null = null;
  for (const [kw, id] of METRIC_KEYWORDS) {
    if (q.includes(kw)) { metric = id; break; }
  }
  const metricLabel = metric ? (METRIC_LABELS[metric] ?? metric) : null;

  // 分頁
  let tab = "financial";
  for (const [kw, t] of Object.entries(TAB_KEYWORDS)) {
    if (q.includes(kw)) { tab = t; break; }
  }

  return { ordered: [], period, year, tab, metric, metricLabel };
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
