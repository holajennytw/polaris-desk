"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { fmtPeriodLabel, fmtRevenue, fmtYoy } from "@/lib/formatters";
import type { FinancialRow } from "@/types/api";

export type { FinancialRow };

export function useFinancials(ticker: string | null, limit = 200) {
  const key = ticker ? `financials-${ticker}-${limit}` : null;
  const { data, isLoading } = useSWR<FinancialRow[]>(
    key,
    () => api.financials(ticker!, limit),
    { revalidateOnFocus: false },
  );
  return { rows: data ?? [], isLoading: !!ticker && isLoading };
}

// 從 query 文字 + 已知公司清單推斷 ticker（前端版；完整版在後端 detect_tickers）
export function inferTickerFromQuery(
  query: string,
  companies: Array<{ id: string; name: string }>,
): string | null {
  const found = companies.find(c => query.includes(c.id) || (c.name && query.includes(c.name)));
  return found?.id ?? null;
}

// FinancialRow[] → 顯示用 KPI 摘要（最新期別）
export function financialsToKpis(rows: FinancialRow[]): Array<{
  label: string; value: string; unit: string; delta: string; trend: "up" | "down"; cite: string;
}> {
  if (!rows.length) return [];

  const periods = [...new Set(rows.map(r => r.fiscal_period).filter(Boolean))].sort();
  const latestPeriod = periods.at(-1);
  const periodRows = rows.filter(r => r.fiscal_period === latestPeriod);
  const get = (id: string) => periodRows.find(r => r.metric_id === id) ?? null;

  const firstRow = periodRows[0];
  const periodLabel = fmtPeriodLabel(latestPeriod, firstRow?.year, firstRow?.month);

  const result = [];
  const revRow = get("revenue");
  if (revRow?.value != null) {
    result.push({
      label: `月營收 ${periodLabel}`,
      value: fmtRevenue(revRow.value),
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
