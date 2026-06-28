"use client";
import { useMemo } from "react";
import type { PeerCompareTrendPoint } from "@/types/api";
import type { ChartPointVM } from "@/types/viewmodel";
import { fmtTrendValue, type BarDatum, type SingleBarDatum } from "@/lib/chartUtils";
import { toLabel } from "@/lib/fieldUtils";
import { fmtFinNum } from "@/lib/formatters";

// ── Grouped Bar Chart (peer comparison) ──────────────────────────

interface PeerGroupedBarChartProps {
  data: BarDatum[];
  aName: string;
  bName: string;
}

export function PeerGroupedBarChart({ data, aName, bName }: PeerGroupedBarChartProps) {
  const allAbsVals = data
    .flatMap(d => [d.aVal !== null ? Math.abs(d.aVal) : null, d.bVal !== null ? Math.abs(d.bVal) : null])
    .filter((v): v is number => v !== null);
  const maxAbs = Math.max(...allAbsVals, 1);
  const pct = (v: number | null) => v !== null ? Math.max((Math.abs(v) / maxAbs) * 100, 4) : 0;
  const neg = (v: number | null) => v !== null && v < 0;

  return (
    <div className="fchart-wrap">
      <div className="fchart-legend">
        <span className="fchart-leg-dot" data-series="a"/>{aName}
        <span className="fchart-leg-dot" data-series="b" style={{ marginLeft: 14 }}/>{bName}
      </div>
      <div className="fchart-grouped-bars">
        {data.map((d, i) => (
          <div key={i} className="fchart-gcol">
            <div className="fchart-gpair">
              <div className="fchart-bar-col">
                {d.aVal !== null && (
                  <span className="fchart-bar-val" data-neg={neg(d.aVal) ? "true" : undefined}>{fmtFinNum(d.aRaw)}</span>
                )}
                <div
                  className="fchart-bar"
                  data-series="a"
                  data-neg={neg(d.aVal) ? "true" : undefined}
                  style={{ height: d.aVal !== null ? pct(d.aVal) + "%" : "0%" }}
                />
              </div>
              <div className="fchart-bar-col">
                {d.bVal !== null && (
                  <span className="fchart-bar-val" data-neg={neg(d.bVal) ? "true" : undefined}>{fmtFinNum(d.bRaw)}</span>
                )}
                <div
                  className="fchart-bar"
                  data-series="b"
                  data-neg={neg(d.bVal) ? "true" : undefined}
                  style={{ height: d.bVal !== null ? pct(d.bVal) + "%" : "0%" }}
                />
              </div>
            </div>
            <div className="fchart-gcol-label">{d.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Trend Line Chart (SVG) ────────────────────────────────────────

interface TrendLineChartProps {
  trend: PeerCompareTrendPoint[];
  aName: string;
  bName: string;
}

export function TrendLineChart({ trend, aName, bName }: TrendLineChartProps) {
  const metrics = useMemo(() => [...new Set(trend.map(t => t.metric))], [trend]);
  return (
    <div>
      <div className="fchart-legend" style={{ marginBottom: 16 }}>
        <span className="fchart-leg-dot" data-series="a"/>{aName}
        <span className="fchart-leg-dot" data-series="b" style={{ marginLeft: 14 }}/>{bName}
      </div>
      {metrics.map(metric => {
        const label = toLabel(metric);
        const pts = trend
          .filter(t => t.metric === metric && (t.a_value !== null || t.b_value !== null))
          .sort((a, b) => a.period.localeCompare(b.period));
        if (pts.length < 2) return null;
        return (
          <div key={metric} className="fchart-metric-section">
            <div className="fchart-metric-title">{label}</div>
            <MetricLineChart pts={pts} metricLabel={label} aName={aName} bName={bName}/>
          </div>
        );
      })}
    </div>
  );
}

interface MetricPt { period: string; a_value: number | null; b_value: number | null }

function MetricLineChart({
  pts, metricLabel, aName, bName,
}: { pts: MetricPt[]; metricLabel: string; aName: string; bName: string }) {
  const W = 560, H = 180, ml = 58, mr = 16, mt = 20, mb = 36;
  const pw = W - ml - mr;
  const ph = H - mt - mb;

  const allVals = pts.flatMap(p => [p.a_value, p.b_value]).filter((v): v is number => v !== null);
  if (!allVals.length) return null;

  const rawMin = Math.min(...allVals);
  const rawMax = Math.max(...allVals);
  const pad = (rawMax - rawMin) * 0.15 || Math.abs(rawMax) * 0.1 || 1;
  const minV = rawMin - pad;
  const maxV = rawMax + pad;
  const range = maxV - minV || 1;

  const xOf = (i: number) => ml + (i / Math.max(pts.length - 1, 1)) * pw;
  const yOf = (v: number) => mt + ph - ((v - minV) / range) * ph;

  const ticks = [0, 1, 2, 3].map(i => {
    const v = minV + (i / 3) * range;
    return { y: yOf(v), label: fmtTrendValue(v, metricLabel) };
  });

  const aPoints = pts
    .map((p, i) => p.a_value !== null ? `${xOf(i).toFixed(1)},${yOf(p.a_value).toFixed(1)}` : null)
    .filter(Boolean) as string[];
  const bPoints = pts
    .map((p, i) => p.b_value !== null ? `${xOf(i).toFixed(1)},${yOf(p.b_value).toFixed(1)}` : null)
    .filter(Boolean) as string[];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="fchart-svg" aria-label={metricLabel}>
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={ml} y1={t.y.toFixed(1)} x2={W - mr} y2={t.y.toFixed(1)} className="fchart-grid"/>
          <text x={ml - 6} y={t.y + 4} className="fchart-axis-y" textAnchor="end">{t.label}</text>
        </g>
      ))}
      <line x1={ml} y1={H - mb} x2={W - mr} y2={H - mb} className="fchart-axis-line"/>
      {pts.map((p, i) => (
        <text key={i} x={xOf(i).toFixed(1)} y={H - 4} className="fchart-axis-x" textAnchor="middle">
          {p.period}
        </text>
      ))}
      {aPoints.length >= 2 && (
        <polyline points={aPoints.join(" ")} className="fchart-line" data-series="a"/>
      )}
      {bPoints.length >= 2 && (
        <polyline points={bPoints.join(" ")} className="fchart-line" data-series="b"/>
      )}
      {pts.map((p, i) => (
        <g key={i}>
          {p.a_value !== null && (
            <circle cx={xOf(i).toFixed(1)} cy={yOf(p.a_value).toFixed(1)} r={4} className="fchart-dot" data-series="a">
              <title>{p.period} · {aName}: {fmtTrendValue(p.a_value, metricLabel)}</title>
            </circle>
          )}
          {p.b_value !== null && (
            <circle cx={xOf(i).toFixed(1)} cy={yOf(p.b_value).toFixed(1)} r={4} className="fchart-dot" data-series="b">
              <title>{p.period} · {bName}: {fmtTrendValue(p.b_value, metricLabel)}</title>
            </circle>
          )}
        </g>
      ))}
    </svg>
  );
}

// ── Single-series Trend Line Chart (research chart[]) ────────────

interface ResearchTrendChartProps {
  data: ChartPointVM[];
}

export function ResearchTrendChart({ data }: ResearchTrendChartProps) {
  if (data.length < 2) return null;

  const W = 560, H = 180, ml = 52, mr = 16, mt = 20, mb = 36;
  const pw = W - ml - mr;
  const ph = H - mt - mb;

  const vals = data.map(d => d.value);
  const rawMin = Math.min(...vals);
  const rawMax = Math.max(...vals);
  const pad = (rawMax - rawMin) * 0.15 || Math.abs(rawMax) * 0.1 || 1;
  const minV = rawMin - pad;
  const maxV = rawMax + pad;
  const range = maxV - minV || 1;

  const xOf = (i: number) => ml + (i / Math.max(data.length - 1, 1)) * pw;
  const yOf = (v: number) => mt + ph - ((v - minV) / range) * ph;

  const ticks = [0, 1, 2, 3].map(i => {
    const v = minV + (i / 3) * range;
    return { y: yOf(v), label: fmtFinNum(Number.isInteger(v) ? String(v) : v.toFixed(1)) };
  });

  const points = data.map((d, i) => `${xOf(i).toFixed(1)},${yOf(d.value).toFixed(1)}`);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="fchart-svg" aria-label="指標走勢">
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={ml} y1={t.y.toFixed(1)} x2={W - mr} y2={t.y.toFixed(1)} className="fchart-grid"/>
          <text x={ml - 6} y={t.y + 4} className="fchart-axis-y" textAnchor="end">{t.label}</text>
        </g>
      ))}
      <line x1={ml} y1={H - mb} x2={W - mr} y2={H - mb} className="fchart-axis-line"/>
      {data.map((d, i) => (
        <text key={i} x={xOf(i).toFixed(1)} y={H - 4} className="fchart-axis-x" textAnchor="middle">
          {d.label}
        </text>
      ))}
      <polyline points={points.join(" ")} className="fchart-line" data-series="a"/>
      {data.map((d, i) => (
        <circle key={i} cx={xOf(i).toFixed(1)} cy={yOf(d.value).toFixed(1)} r={4} className="fchart-dot" data-series="a">
          <title>{d.label}: {fmtFinNum(d.value)}</title>
        </circle>
      ))}
    </svg>
  );
}

// ── Single Bar Chart (research KPI) ──────────────────────────────

interface ResearchBarChartProps {
  data: SingleBarDatum[];
}

export function ResearchBarChart({ data }: ResearchBarChartProps) {
  if (!data.length) return null;
  const maxAbs = Math.max(...data.map(d => Math.abs(d.value)), 1);
  const pct = (v: number) => Math.max((Math.abs(v) / maxAbs) * 100, 4);

  return (
    <div className="fchart-wrap fchart-single">
      <div className="fchart-grouped-bars">
        {data.map((d, i) => (
          <div key={i} className="fchart-gcol">
            <div className="fchart-gpair fchart-single-pair">
              <div className="fchart-bar-col">
                <span className="fchart-bar-val" data-neg={d.isNeg ? "true" : undefined}>
                  {fmtFinNum(d.raw)}{d.unit && <span className="fchart-bar-unit">{d.unit}</span>}
                </span>
                <div
                  className="fchart-bar"
                  data-series="a"
                  data-neg={d.isNeg ? "true" : undefined}
                  style={{ height: pct(d.value) + "%" }}
                />
              </div>
            </div>
            <div className="fchart-gcol-label">{d.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
