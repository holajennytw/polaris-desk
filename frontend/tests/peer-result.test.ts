import assert from "node:assert/strict";
import test from "node:test";

import {
  metricForPeriod,
  normalizePeerCompare,
  peerCitations,
} from "../src/lib/peer-result.ts";
import { parseQuery } from "../src/lib/peer.ts";

test("metricForPeriod returns the selected quarter instead of the latest quarter", () => {
  const rows = [
    { fiscal_period: "2026Q1", metric_id: "revenue_yoy", value: 43.6 },
    { fiscal_period: "2025Q4", metric_id: "revenue_yoy", value: 12.3 },
  ];

  assert.equal(metricForPeriod(rows, "revenue_yoy", "2025Q4"), 12.3);
});

test("peerCitations exposes and de-duplicates financial and call sources", () => {
  const result = {
    kpis: [
      {
        label: "毛利率",
        a: { v: "57.8%", citations: [{ src: "fin-2330-2025Q4", page: "2025Q4" }] },
        b: { v: "38.3%", citations: [{ src: "fin-2454-2025Q4", page: "2025Q4" }] },
      },
    ],
    calls: [
      {
        a: { quote: "先進製程需求成長。", cite: "chunk-2330" },
        b: { quote: "邊緣 AI 需求成長。", cite: "chunk-2454" },
      },
    ],
  };

  assert.deepEqual(peerCitations(result), [
    { sourceId: "fin-2330-2025Q4", label: "毛利率", detail: "2025Q4" },
    { sourceId: "fin-2454-2025Q4", label: "毛利率", detail: "2025Q4" },
    { sourceId: "chunk-2330", label: "法說會", detail: "先進製程需求成長。" },
    { sourceId: "chunk-2454", label: "法說會", detail: "邊緣 AI 需求成長。" },
  ]);
});

test("normalizePeerCompare follows the actual FastAPI response contract", () => {
  const raw = {
    a_ticker: "2330",
    b_ticker: "2454",
    fiscal_period: "2025Q4",
    kpis: [{
      label: "毛利率",
      a: { v: "57.8%", citations: [{ src: "fin-a", page: "2025Q4" }] },
      b: { v: "38.3%", citations: [{ src: "fin-b", page: "2025Q4" }] },
      diff: "19.5pp",
      better: "a",
    }],
    financial: [],
    calls: [{
      dim: "法說會",
      topic: "毛利率",
      a: { stance: "有相關引用", tone: "neu", quote: "A 原文", cite: "chunk-a" },
      b: { stance: "有相關引用", tone: "neu", quote: "B 原文", cite: "chunk-b" },
    }],
    trend: [],
    valuation: [],
    summary: "摘要",
    compliance_status: "passed",
  };

  const result = normalizePeerCompare(raw);
  assert.equal(result.kpis[0].label, "毛利率");
  assert.equal(result.kpis[0].a.citations[0].page, "2025Q4");
  assert.equal(result.calls[0].a.quote, "A 原文");
});

test("parseQuery leaves period empty unless the user explicitly supplies one", () => {
  assert.equal(parseQuery("比較台積電與聯發科毛利率").period, "");
  assert.equal(parseQuery("比較台積電與聯發科 2025Q4 毛利率").period, "2025 Q4");
});
