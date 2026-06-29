import type {
  BackendPeerCompareResponse,
  PeerCompareResult,
} from "@/types/api";

export interface FinancialMetricRow {
  fiscal_period: string;
  metric_id: string;
  value: number;
}

export interface PeerSource {
  sourceId: string;
  label: string;
  detail: string;
  snippet: string;
}

interface PeerResultLike {
  kpis: Array<{
    label: string;
    a: { v?: string; citations: Array<{ src: string; page: string }> };
    b: { v?: string; citations: Array<{ src: string; page: string }> };
  }>;
  calls: Array<{
    a: { quote: string; cite: string };
    b: { quote: string; cite: string };
  }>;
}

export function metricForPeriod(
  rows: FinancialMetricRow[],
  metricId: string,
  fiscalPeriod: string,
): number | null {
  return rows.find(
    (row) => row.fiscal_period === fiscalPeriod && row.metric_id === metricId,
  )?.value ?? null;
}

export function peerCitations(result: PeerResultLike | null): PeerSource[] {
  if (!result) return [];

  const sources: PeerSource[] = [];
  const seen = new Set<string>();
  const add = (source: PeerSource) => {
    if (!source.sourceId || seen.has(source.sourceId)) return;
    seen.add(source.sourceId);
    sources.push(source);
  };

  result.kpis.forEach((kpi) => {
    kpi.a.citations.forEach((citation) => {
      add({
        sourceId: citation.src,
        label: citation.src,
        detail: kpi.label,
        snippet: [kpi.label, kpi.a.v, citation.page].filter(Boolean).join("　"),
      });
    });
    kpi.b.citations.forEach((citation) => {
      add({
        sourceId: citation.src,
        label: citation.src,
        detail: kpi.label,
        snippet: [kpi.label, kpi.b.v, citation.page].filter(Boolean).join("　"),
      });
    });
  });
  result.calls.forEach((call) => {
    [call.a, call.b].forEach((side) => {
      add({
        sourceId: side.cite,
        label: side.cite || "法說會",
        detail: "法說會逐字稿",
        snippet: side.quote,
      });
    });
  });

  return sources;
}

export function normalizePeerCompare(raw: BackendPeerCompareResponse): PeerCompareResult {
  return {
    a_ticker: raw.a_ticker,
    b_ticker: raw.b_ticker,
    fiscal_period: raw.fiscal_period,
    kpis: raw.kpis.map((k) => ({
      label: k.label,
      a: { v: k.a.v, citations: k.a.citations.map((c) => ({ src: c.src, page: c.page })) },
      b: { v: k.b.v, citations: k.b.citations.map((c) => ({ src: c.src, page: c.page })) },
      diff: k.diff,
      better: k.better,
    })),
    financial: raw.financial.map((f) => ({
      metric: f.metric,
      a: { v: f.a.v, citations: f.a.citations.map((c) => ({ src: c.src, page: c.page })) },
      b: { v: f.b.v, citations: f.b.citations.map((c) => ({ src: c.src, page: c.page })) },
      better: f.better,
      note: f.note,
    })),
    calls: raw.calls.map((c) => ({
      dim: c.dim,
      topic: c.topic,
      a: { stance: c.a.stance, tone: c.a.tone, quote: c.a.quote, cite: c.a.cite },
      b: { stance: c.b.stance, tone: c.b.tone, quote: c.b.quote, cite: c.b.cite },
    })),
    calls_period: raw.calls_period ?? null,
    trend: raw.trend,
    valuation: raw.valuation,
    summary: raw.summary,
    compliance_status: raw.compliance_status,
  };
}
