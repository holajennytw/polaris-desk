// ============================================================
// lib/peer.ts — 前端同業比較工具函式
// buildComparison: 組合兩家公司的對比資料（mock 情境直接從 JSON 取）
// parseQuery: 解析自然語言查詢，抽出公司、季別、分頁
// ============================================================
import type { ComparisonVM } from "@/types/viewmodel";

// 公司名稱對映（NLP 別名）— 與後端 _COMPANY_NAMES 保持一致
const COMPANY_ALIASES: Record<string, string> = {
  "台積電": "2330", "tsmc": "2330", "TSMC": "2330", "台積": "2330",
  "鴻海": "2317", "foxconn": "2317", "Foxconn": "2317",
  "聯發科": "2454", "mediatek": "2454", "MediaTek": "2454",
  "聯詠": "3034", "novatek": "3034", "Novatek": "3034",
};

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
  tab: string;
}

export function parseQuery(q: string): ParsedQuery {
  const found: Array<{ id: string; name: string; status: "ok" | "nodata" }> = [];
  const lower = q.toLowerCase();

  // 找公司
  for (const [alias, id] of Object.entries(COMPANY_ALIASES)) {
    if (q.includes(alias) || lower.includes(alias.toLowerCase())) {
      if (!found.find((f) => f.id === id)) {
        found.push({ id, name: alias, status: "ok" });
      }
    }
  }

  // 季別
  // 只有 query 明確包含季度才填入；否則回空字串，由呼叫端沿用目前 fiscalPeriod。
  let period = "";
  const pm = q.match(PERIOD_PATTERN);
  if (pm) period = `${pm[1]} Q${pm[2]}`;

  // 分頁
  let tab = "financial";
  for (const [kw, t] of Object.entries(TAB_KEYWORDS)) {
    if (q.includes(kw)) { tab = t; break; }
  }

  return { ordered: found, period, tab };
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
