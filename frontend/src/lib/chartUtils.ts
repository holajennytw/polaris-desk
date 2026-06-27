import type { PeerCompareTrendPoint } from "@/types/api";
import type { KpiVM } from "@/types/viewmodel";
import { fmtFinNum } from "@/lib/formatters";

/** Parse string metric value (strips %, commas) → null if qualitative or "—" */
export function parseMetricValue(v: string | null | undefined): number | null {
  if (!v) return null;
  const t = v.trim();
  if (!t || t === "—") return null;
  if (/[一-鿿]/.test(t)) return null;
  const cleaned = t.replace(/[,，\s]/g, "").replace(/%$/, "").replace(/^\+/, "");
  const n = parseFloat(cleaned);
  return isNaN(n) ? null : n;
}

/** Format trend numeric value for display (% vs 億) */
export function fmtTrendValue(v: number | null, metricLabel: string): string {
  if (v === null) return "—";
  if (metricLabel.includes("率") || metricLabel.includes("YoY") || metricLabel.includes("%")) {
    return fmtFinNum(`${v.toFixed(2)}%`);
  }
  const yi = v / 100_000;
  return fmtFinNum(`${yi >= 100 ? yi.toFixed(0) : yi.toFixed(1)} 億`);
}

export interface BarDatum {
  label: string;
  aVal: number | null;
  bVal: number | null;
  aRaw: string;
  bRaw: string;
}

export interface SingleBarDatum {
  label: string;
  value: number;
  raw: string;
  unit: string;
  isNeg: boolean;
}

/** Build grouped bar data for peer comparison */
export function toPeerBarData(
  rows: Array<{ label: string; aRaw: string; bRaw: string }>,
): BarDatum[] {
  return rows
    .map(r => ({
      label: r.label,
      aVal: parseMetricValue(r.aRaw),
      bVal: parseMetricValue(r.bRaw),
      aRaw: r.aRaw,
      bRaw: r.bRaw,
    }))
    .filter(d => d.aVal !== null || d.bVal !== null);
}

/** Build single-series bar data from research KPIs */
export function toSingleBarData(kpis: KpiVM[]): SingleBarDatum[] {
  return kpis
    .map(k => {
      const v = parseMetricValue(k.value);
      if (v === null) return null;
      return { label: k.label, value: v, raw: k.value, unit: k.unit, isNeg: v < 0 };
    })
    .filter((d): d is SingleBarDatum => d !== null);
}

/** Can we draw a peer grouped bar chart? At least 1 parseable pair. */
export function canGroupedBarChart(rows: Array<{ aRaw: string; bRaw: string }>): boolean {
  return rows.some(r => parseMetricValue(r.aRaw) !== null || parseMetricValue(r.bRaw) !== null);
}

/** Can we draw a research single-bar chart? At least 2 parseable values. */
export function canSingleBarChart(kpis: KpiVM[]): boolean {
  return kpis.filter(k => parseMetricValue(k.value) !== null).length >= 2;
}

/** Can we draw a trend line chart? At least one metric with >= 2 periods. */
export function canLineChart(trend: PeerCompareTrendPoint[]): boolean {
  const metrics = [...new Set(trend.map(t => t.metric))];
  return metrics.some(m => {
    const pts = trend.filter(t => t.metric === m && (t.a_value !== null || t.b_value !== null));
    return pts.length >= 2;
  });
}
