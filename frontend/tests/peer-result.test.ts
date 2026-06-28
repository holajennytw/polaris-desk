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
    { sourceId: "fin-2330-2025Q4", label: "fin-2330-2025Q4", detail: "毛利率", snippet: "毛利率　57.8%　2025Q4" },
    { sourceId: "fin-2454-2025Q4", label: "fin-2454-2025Q4", detail: "毛利率", snippet: "毛利率　38.3%　2025Q4" },
    { sourceId: "chunk-2330", label: "chunk-2330", detail: "法說會逐字稿", snippet: "先進製程需求成長。" },
    { sourceId: "chunk-2454", label: "chunk-2454", detail: "法說會逐字稿", snippet: "邊緣 AI 需求成長。" },
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
      better: "a" as "a",
    }],
    financial: [],
    calls: [{
      dim: "法說會",
      topic: "毛利率",
      a: { stance: "有相關引用", tone: "neu" as "neu", quote: "A 原文", cite: "chunk-a" },
      b: { stance: "有相關引用", tone: "neu" as "neu", quote: "B 原文", cite: "chunk-b" },
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
  assert.equal(parseQuery("比較台積電與聯發科 2025Q4 毛利率").period, "2025Q4");
});

test("parseQuery recognizes 全年 / 年度 / 年 as a year (no explicit quarter)", () => {
  // 「2025全年」曾因 /(\d{4})年/ 只認「2025年」而漏掉，導致回退到最新季 → 答非所問
  assert.equal(parseQuery("2025全年 EPS").year, 2025);
  assert.equal(parseQuery("2025全年 EPS").period, "");
  assert.equal(parseQuery("2025年度毛利率").year, 2025);
  assert.equal(parseQuery("2025年毛利率").year, 2025);
});

test("parseQuery does not mistake a 4-digit ticker for a year", () => {
  // 「2330」是股號不是年份；沒有 年/全年/年度 後綴就不該當年份
  assert.equal(parseQuery("比較 2330 與 2317 EPS").year, null);
});

test("parseQuery extracts the requested metric id when named", () => {
  assert.equal(parseQuery("2025全年 EPS").metric, "eps");
  assert.equal(parseQuery("比較台積電與聯發科毛利率").metric, "gross_margin");
  assert.equal(parseQuery("淨利率比較").metric, "net_margin");
  // 沒有指名特定指標時為 null
  assert.equal(parseQuery("比較鴻海與台達電").metric, null);
});
