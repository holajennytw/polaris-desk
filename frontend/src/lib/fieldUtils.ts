// ============================================================
// lib/fieldUtils.ts — 共用「有值才顯示」工具 + 欄位名稱對照表
// ============================================================

/**
 * 有值才顯示的核心判斷。
 * null / undefined / "" / "—" / [] → false（無資料，不渲染）
 * 0、"0"、"0.0"、"0%" 等合法數值 → true
 */
export function hasValue(v: unknown): boolean {
  if (v === null || v === undefined) return false;
  if (typeof v === "string") {
    const t = v.trim();
    return t !== "" && t !== "—";
  }
  if (Array.isArray(v)) return v.length > 0;
  return true;
}

/**
 * 後端英文欄位名 → 中文名稱對照表（Field Dictionary）。
 * 對應 r6_financial_metric.metric_name 及 r6_disclosure_event.event_type_name。
 * doc_type / source_key / event_key 的轉換見 lib/adapters.ts。
 */
export const METRIC_DICT: Record<string, string> = {
  // 月營收類（r6_financial_metric）
  revenue:          "月營收",
  revenue_yoy:      "月營收 YoY",
  ytd_yoy:          "累計 YoY",
  // 損益類
  gross_profit:     "毛利額",
  gross_margin:     "毛利率",
  op_income:        "營業利益",
  op_margin:        "營業利益率",
  net_income:       "淨利",
  net_margin:       "淨利率",
  eps:              "EPS",
  eps_yoy:          "EPS YoY",
  // 估值類
  pe:               "本益比 PE",
  pb:               "股價淨值比 PB",
  ev_ebitda:        "EV / EBITDA",
  roe:              "ROE",
  // 事件類型（r6_disclosure_event.event_type_name）
  earnings_call:    "法說會",
  major_news:       "重大訊息",
  monthly_revenue:  "月營收公告",
  transcript:       "法說逐字稿",
  fin:              "合併財報",
  news:             "新聞",
};

/** 後端英文欄位名 → 中文；查無對照時回傳原值 */
export function toLabel(raw: string): string {
  return METRIC_DICT[raw] ?? raw;
}
