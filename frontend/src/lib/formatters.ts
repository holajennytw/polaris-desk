// 財務數字格式化 — 集中管理，取代 peer/page.tsx 與 useFinancials.ts 的散落版本

/** 千元 → 億元顯示，例：439_105_000 → "4,391.1" */
export function fmtRevenue(valueInThousands: number | null | undefined): string {
  if (valueInThousands == null) return "—";
  const yi = valueInThousands / 100_000;
  return yi >= 100 ? yi.toFixed(0) : yi.toFixed(1);
}

/** YoY % 顯示，例：12.34 → "+12.34%"，-3.5 → "-3.50%" */
export function fmtYoy(value: number | null | undefined): string {
  if (value == null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

/** EPS 顯示，例：12.54 → "12.54 元" */
export function fmtEps(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value.toFixed(2)} 元`;
}

/** YYYYMM → "YYYY-MM"，例：202504 → "2025-04" */
export function fmtYearMonth(yyyymm: number | null | undefined): string {
  if (yyyymm == null) return "";
  return String(yyyymm).replace(/^(\d{4})(\d{2})$/, "$1-$2");
}

/** fiscal_period + year/month → 可讀標籤，例："2025Q4" 或 "2025年4月" */
export function fmtPeriodLabel(
  fiscalPeriod: string | null | undefined,
  year?: number | null,
  month?: number | null,
): string {
  if (year != null && month != null) return `${year}年${month}月`;
  return fiscalPeriod ?? "";
}
