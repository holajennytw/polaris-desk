// 財務數字格式化 — 集中管理，取代 peer/page.tsx 與 useFinancials.ts 的散落版本

/**
 * 財務數值千分位格式化（Presentation Layer Only）。
 * - null / "" / "—" → "—"
 * - 無法解析為數值（質性值）→ 原樣返回
 * - 整數部分 ≥ 4 位 → 加千分位分隔符，小數位數與正負號原樣保留
 * - 後綴（%, 元, 億 等）原樣保留
 */
export function fmtFinNum(raw: string | number | null | undefined): string {
  if (raw == null || raw === "") return "—";
  const s = String(raw).trim();
  if (!s || s === "—") return "—";
  const m = s.match(/^([+\-]?)([\d,]+(?:\.\d+)?)(.*)$/);
  if (!m) return s;
  const [, sign, numStr, suffix] = m;
  const clean = numStr.replace(/,/g, "");
  const dotIdx = clean.indexOf(".");
  const intPart = dotIdx >= 0 ? clean.slice(0, dotIdx) : clean;
  const decPart = dotIdx >= 0 ? clean.slice(dotIdx) : "";
  const intNum = parseInt(intPart, 10);
  if (isNaN(intNum)) return s;
  const intFormatted = intPart.length >= 4 ? intNum.toLocaleString("en-US") : intPart;
  return `${sign}${intFormatted}${decPart}${suffix}`;
}

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

/** fiscal_period → 下拉選單顯示標籤
 *  有月份：「2026年 Q2 · 5月」
 *  無月份：「2026年 Q2」
 *  無法解析：回傳原始字串
 */
export function fmtPeriodOption(fiscalPeriod: string, month?: number | null): string {
  const m = fiscalPeriod.match(/^(\d{4})Q([1-4])$/);
  if (!m) return fiscalPeriod;
  const [, year, q] = m;
  const base = `${year}年 Q${q}`;
  return month != null ? `${base} · ${month}月` : base;
}
