"use client";
import useSWR from "swr";
import { API_BASE } from "@/lib/config";

export interface FinancialRow {
  ticker: string;
  fiscal_period: string | null;
  metric_id: string | null;
  value: number | null;
  unit: string | null;
  source_id: string | null;
  published_at: string | null;
  year: number | null;
  month: number | null;
}

async function fetchFinancials(ticker: string): Promise<FinancialRow[]> {
  const res = await fetch(`${API_BASE}/financials?ticker=${ticker}&limit=30`);
  if (!res.ok) return [];
  return res.json();
}

export function useFinancials(ticker: string | null) {
  const key = ticker ? `financials-${ticker}` : null;
  const { data, isLoading } = useSWR<FinancialRow[]>(key, () => fetchFinancials(ticker!), {
    revalidateOnFocus: false,
  });
  return { rows: data ?? [], isLoading: !!ticker && isLoading };
}

// 從 query 文字 + 已知公司清單推斷 ticker
export function inferTickerFromQuery(
  query: string,
  companies: Array<{ id: string; name: string }>
): string | null {
  // 先試直接 4 碼數字（非年份）
  const found = companies.find(c => {
    if (query.includes(c.id)) return true;
    if (c.name && query.includes(c.name)) return true;
    return false;
  });
  return found?.id ?? null;
}

// FinancialRow[] → 顯示用 KPI 摘要（最新期別）
export function financialsToKpis(rows: FinancialRow[]): Array<{
  label: string; value: string; unit: string; delta: string; trend: "up" | "down"; cite: string;
}> {
  if (!rows.length) return [];

  // 取最新期別
  const periods = [...new Set(rows.map(r => r.fiscal_period).filter(Boolean))].sort();
  const latestPeriod = periods.at(-1);
  const periodRows = rows.filter(r => r.fiscal_period === latestPeriod);
  const get = (id: string) => periodRows.find(r => r.metric_id === id) ?? null;

  // 優先用 v_financial_metrics_semantic 的 year + month，沒有時 fallback 到 fiscal_period
  const firstRow = periodRows[0];
  const periodLabel =
    firstRow?.year != null && firstRow?.month != null
      ? `${firstRow.year}年${firstRow.month}月`
      : (latestPeriod ?? "");

  const result = [];
  const revRow = get("revenue");
  if (revRow?.value != null) {
    const yi = revRow.value / 100_000; // 千元 → 億元
    result.push({
      label: `月營收 ${periodLabel}`,
      value: yi >= 100 ? yi.toFixed(0) : yi.toFixed(1),
      unit: "億元",
      delta: "",
      trend: "up" as const,
      cite: revRow.source_id ?? "",
    });
  }
  const yoyRow = get("revenue_yoy");
  if (yoyRow?.value != null) {
    result.push({
      label: `月營收 YoY ${periodLabel}`,
      value: yoyRow.value.toFixed(2),
      unit: "%",
      delta: "",
      trend: yoyRow.value >= 0 ? ("up" as const) : ("down" as const),
      cite: yoyRow.source_id ?? "",
    });
  }
  const ytdRow = get("ytd_yoy");
  if (ytdRow?.value != null) {
    result.push({
      label: `累計 YoY ${periodLabel}`,
      value: ytdRow.value.toFixed(2),
      unit: "%",
      delta: "",
      trend: ytdRow.value >= 0 ? ("up" as const) : ("down" as const),
      cite: ytdRow.source_id ?? "",
    });
  }
  return result;
}
