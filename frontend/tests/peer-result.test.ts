import assert from "node:assert/strict";
import test from "node:test";

import { metricForPeriod, peerCitations } from "../src/lib/peer-result.ts";

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
