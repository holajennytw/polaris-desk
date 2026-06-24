export interface FinancialMetricRow {
  fiscal_period: string;
  metric_id: string;
  value: number;
}

export interface PeerSource {
  sourceId: string;
  label: string;
  detail: string;
}

interface PeerResultLike {
  kpis: Array<{
    label: string;
    a: { citations: Array<{ src: string; page: string }> };
    b: { citations: Array<{ src: string; page: string }> };
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
    [...kpi.a.citations, ...kpi.b.citations].forEach((citation) => {
      add({ sourceId: citation.src, label: kpi.label, detail: citation.page });
    });
  });
  result.calls.forEach((call) => {
    [call.a, call.b].forEach((side) => {
      add({ sourceId: side.cite, label: "法說會", detail: side.quote });
    });
  });

  return sources;
}
