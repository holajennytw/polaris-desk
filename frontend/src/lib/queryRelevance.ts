// Maps keyword groups to metric label patterns.
// Both sides must hit the same group to score.
const METRIC_GROUPS: Array<{ keywords: string[]; patterns: string[] }> = [
  { keywords: ["營收", "revenue", "收入", "月收"],       patterns: ["營收", "收入"] },
  { keywords: ["毛利", "毛利率", "gross"],              patterns: ["毛利"] },
  { keywords: ["營業利益", "營益率", "operating"],       patterns: ["營業利益", "營益"] },
  { keywords: ["EPS", "每股盈餘", "稅後純益", "每股"],   patterns: ["EPS", "每股"] },
  { keywords: ["資本支出", "capex", "投資支出"],         patterns: ["資本支出"] },
  { keywords: ["研發", "R&D"],                         patterns: ["研發"] },
  { keywords: ["YoY", "年增", "成長率", "年成長"],       patterns: ["YoY", "年增", "成長"] },
  { keywords: ["ROE", "股東權益報酬"],                  patterns: ["ROE"] },
  { keywords: ["ROA", "資產報酬"],                     patterns: ["ROA"] },
  { keywords: ["負債", "debt"],                        patterns: ["負債"] },
  { keywords: ["淨利", "純益", "net income"],          patterns: ["淨利", "純益"] },
];

const FINANCIAL_KEYWORDS = [
  "營收", "收入", "毛利", "EPS", "每股", "YoY", "年增", "成長率",
  "業績", "損益", "獲利", "財務", "利益", "資本支出", "研發費用",
];

/** Returns true if the query is about financial/KPI metrics (not operations or macro). */
export function isFinancialQuery(query: string): boolean {
  return FINANCIAL_KEYWORDS.some(kw => query.includes(kw));
}

/** Scores how relevant a KPI label is to the query. Higher = more relevant. */
export function scoreLabel(label: string, query: string): number {
  let score = 0;
  for (const group of METRIC_GROUPS) {
    if (
      group.keywords.some(kw => query.includes(kw)) &&
      group.patterns.some(p => label.includes(p))
    ) {
      score += 2;
    }
  }
  return score;
}

/** Sorts items by relevance to query (most relevant first). Stable for equal scores. */
export function sortByRelevance<T extends { label: string }>(items: T[], query: string): T[] {
  if (!query) return items;
  return [...items].sort((a, b) => scoreLabel(b.label, query) - scoreLabel(a.label, query));
}

/** Sorts financial rows (keyed by `metric` field) by relevance. */
export function sortFinancialByRelevance<T extends { metric: string }>(items: T[], query: string): T[] {
  if (!query) return items;
  return [...items].sort((a, b) => scoreLabel(b.metric, query) - scoreLabel(a.metric, query));
}

/** Detects which peer tab the query is most relevant to. */
export function detectQueryTab(query: string): "financial" | "calls" | null {
  if (/法說|法人|逐字稿|earnings|transcript/i.test(query)) return "calls";
  if (isFinancialQuery(query)) return "financial";
  return null;
}
