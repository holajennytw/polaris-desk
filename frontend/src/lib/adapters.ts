// ============================================================
// lib/adapters.ts — 後端形狀 → View-Model 正規化（唯一轉換層）
// 元件不直接碰後端形狀，只讀 VM。
// ============================================================
import type {
  AlertRaw, Severity, KpiRaw, SummaryItemRaw, ChartPointRaw,
  ReactStepRaw, AskResponse, AskCitationRaw, NodeTraceRaw,
  CompanyRaw, CompanyResponse,
  NewsItemRaw, NewsResponse, DocRaw, LibraryResponse,
  HistoryItemRaw, NotificationItemRaw, NotificationsResponse,
  ResolveResponse, WatchItemRaw, GroundedValue, CitationRaw,
  ResearchResponse, ResearchCitationRaw, ResearchTraceStepRaw,
} from "@/types/api";
import type {
  AlertVM, AlertLevel, KpiVM, SummaryItemVM, ChartPointVM,
  TraceStepVM, AskVM, CompanyVM, ComparisonVM, NewsItemVM, NewsVM,
  DocVM, LibraryVM, HistoryItemVM, NotificationItemVM, NotificationsVM,
  ResolveVM, WatchItemVM, GroundedVM, CitationVM, CitationTrackerVM,
} from "@/types/viewmodel";

// severity → level
function sevToLevel(s: Severity): AlertLevel {
  if (s === "alert") return "high";
  if (s === "watch") return "mid";
  return "info";
}

// GroundedValue passthrough (already correct shape in our mocks)
function normalizeGrounded(g: GroundedValue): GroundedVM {
  if (typeof g === "string") return g;
  return { v: g.v, citations: g.citations.map((c) => ({ src: c.src, page: c.page })) };
}

export function normalizeAlert(raw: AlertRaw): AlertVM {
  return {
    id: raw.event_id,
    origin: (raw.origin as AlertVM["origin"]) ?? "research",
    level: sevToLevel(raw.severity),
    title: raw.title || (raw.ticker ? `${raw.ticker} · MOPS 監控` : "系統警示"),
    summary: raw.summary,
    source: raw.source || raw.ticker || "MOPS Watchdog",
    time: raw.time ?? "",
    stock: raw.ticker,
  };
}

export function normalizeAlerts(raw: AlertRaw[]): AlertVM[] {
  return raw.map(normalizeAlert);
}

function normalizeKpi(raw: KpiRaw): KpiVM {
  return {
    label: raw.label,
    value: raw.value,
    unit: raw.unit,
    delta: raw.delta,
    trend: raw.trend,
    cite: raw.cite_key,
  };
}

function normalizeSummaryItem(raw: SummaryItemRaw): SummaryItemVM {
  return { text: raw.text, cite: raw.cite_key, page: raw.page };
}

function mapTraceToSteps(steps: ReactStepRaw[]): TraceStepVM[] {
  return steps.map((s) => ({ type: s.type, text: s.text, tool: s.tool }));
}

function nodeTracesToSteps(traces: NodeTraceRaw[]): TraceStepVM[] {
  return traces.map((t) => ({
    type: t.status === "error" ? "OBS" : "ACT",
    text: t.status === "error" && t.error_message
      ? `${t.node_name}: ${t.error_message}`
      : t.node_name,
    tool: true,
  }));
}

// bullet 內文可能夾帶 inline 來源標記（後端兩種慣例並存：
// 「(source_id: XXX)」/ 全形「（來源：XXX）」），用它精準對回 citation，
// 避免用陣列位置猜（見 #75：多期別/公司混答時位置對應會連錯 chunk）。
const INLINE_SOURCE_RE = /[（(](?:source_id|來源)[：:]\s*([^)）]+)[)）]/;

function findInlineCitation<T extends { source_id: string }>(
  text: string,
  pool: T[],
): T | undefined {
  const m = text.match(INLINE_SOURCE_RE);
  if (!m) return undefined;
  const sid = m[1].trim();
  return pool.find((c) => c.source_id === sid);
}

function askCitationToTracker(c: AskCitationRaw, i: number): CitationTrackerVM {
  const label = c.company ?? c.source_id;
  const detail = c.snippet.length > 60 ? c.snippet.slice(0, 60) + "…" : c.snippet;
  return { ix: String(i + 1), label, detail, cite: c.source_id, snippet: c.snippet, period: "" };
}

export function normalizeAsk(raw: AskResponse, query: string): AskVM {
  const bullets = splitAnswer(raw.answer);
  const summary: SummaryItemVM[] = bullets.map((text, i) => {
    const cite = findInlineCitation(text, raw.citations) ?? raw.citations[i];
    return { text, cite: cite?.source_id ?? "", page: "" };
  });
  const retrieval_degraded =
    raw.citations.length === 0 ||
    raw.citations.every((c) => c.origin === "bm25" || c.origin === "stub");
  return {
    query,
    compliance_status: raw.compliance_status,
    retrieval_degraded,
    kpis: [],
    summary,
    chart: [],
    react: nodeTracesToSteps(raw.trace),
    citations: raw.citations.map(askCitationToTracker),
  };
}

export function normalizeCompany(raw: CompanyRaw): CompanyVM {
  return {
    id: raw.ticker,
    name: raw.company_name ?? raw.ticker,
    aliases: raw.aliases ? raw.aliases.split(",").map(a => a.trim()).filter(Boolean) : [],
    provenance: "real",
  };
}

export function normalizeComparison(raw: CompanyResponse): ComparisonVM {
  return {
    meta: raw as any,
    kpis: raw.kpis.map((k) => ({
      label: k.label,
      a: normalizeGrounded(k.a),
      b: normalizeGrounded(k.b),
      diff: k.diff,
      better: k.better,
    })),
    financial: {
      pnl: raw.financial.pnl.map((r) => ({
        metric: r.metric,
        a: normalizeGrounded(r.a),
        b: normalizeGrounded(r.b),
        note: r.note,
      })),
      mix: raw.financial.mix,
    },
    calls: raw.calls,
    news: {
      window: raw.news.window,
      senti: raw.news.senti,
      events: raw.news.events,
      topics: raw.news.topics,
    },
    valuation: raw.valuation,
  };
}

export function normalizeNewsItem(raw: NewsItemRaw): NewsItemVM {
  return {
    id: raw.id,
    cite: raw.source_key,
    title: raw.title,
    summary: raw.summary,
    time: raw.time,
    tags: raw.tags,
    url: raw.url,
  };
}

export function normalizeNews(raw: NewsResponse): NewsVM {
  return {
    updated: raw.updated,
    tabs: raw.tabs,
    items: raw.items.map(normalizeNewsItem),
  };
}

export function normalizeDoc(raw: DocRaw): DocVM {
  return {
    id: raw.id,
    ticker: raw.ticker ?? raw.company ?? "",
    company_name: raw.company_name ?? raw.company ?? "",
    doc_type: raw.doc_type ?? raw.kind ?? "",
    fiscal_period: raw.fiscal_period ?? raw.period ?? "",
    source_file: raw.source_file ?? raw.title ?? "",
    page_count: raw.page_count ?? raw.pages ?? 0,
    published_at: raw.published_at ?? raw.time ?? "",
    fetched_at: raw.fetched_at ?? raw.time ?? "",
    ingested: raw.ingested,
  };
}

export function normalizeLibrary(raw: LibraryResponse): LibraryVM {
  return {
    stats: raw.stats,
    types: raw.types,
    docs: raw.docs.map(normalizeDoc),
  };
}

export function normalizeHistoryItem(raw: HistoryItemRaw): HistoryItemVM {
  return { id: raw.id, query: raw.query, page: raw.page, time: raw.time, tags: raw.tags };
}

export function normalizeNotificationItem(raw: NotificationItemRaw): NotificationItemVM {
  return { id: raw.id, type: raw.type, title: raw.title, body: raw.body, time: raw.time, read: raw.read };
}

export function normalizeNotifications(raw: NotificationsResponse): NotificationsVM {
  return { items: raw.items.map(normalizeNotificationItem), unread: raw.unread_count };
}

export function normalizeResolve(raw: ResolveResponse): ResolveVM {
  return raw;
}

export function normalizeWatchItem(raw: WatchItemRaw): WatchItemVM {
  return {
    id: raw.id,
    stock: raw.stock_id,
    name: raw.name,
    trigger: raw.trigger,
    status: raw.status,
    lastTriggered: raw.last_triggered,
  };
}

// ── /research 端點正規化 ────────────────────────────────────────

// doc_type → 中文（BQ canonical + stub 兩套）
const _DOC_TYPE_LABEL: Record<string, string> = {
  major_news:   "重大訊息",
  transcript:   "法說逐字稿",
  presentation: "法說簡報",
  news:         "新聞",
  fin:          "合併財報",
  call:         "法說簡報",
  perf:         "營運報告",
};

// origin（搜尋方法）→ 中文 fallback
const _ORIGIN_LABEL: Record<ResearchCitationRaw["origin"], string> = {
  stub:      "文件",
  bm25:      "文件",
  embedding: "文件",
  rerank:    "文件",
  colpali:   "法說簡報",
  vision:    "法說簡報",
  news:      "新聞",
};

// #13 新欄位：source_key / event_key → 中文標籤
const _SOURCE_KEY_LABEL: Record<string, string> = {
  PRIMARY_EC_TRANSCRIPT:   "法說逐字稿",
  PRIMARY_EC_PRESENTATION: "法說簡報",
  PRIMARY_MOPS:            "重大訊息",
  PRIMARY_NEWS:            "新聞",
};
const _EVENT_KEY_LABEL: Record<string, string> = {
  earnings_call:        "法說會",
  "major_news.others":  "重大訊息",
  news:                 "新聞",
};

function citationLabel(ev: ResearchCitationRaw): string {
  // 1. source_key（最精確，#13 新欄位）
  if (ev.source_key) return _SOURCE_KEY_LABEL[ev.source_key] ?? ev.source_key;
  // 2. event_key（#13 新欄位）
  if (ev.event_key) return _EVENT_KEY_LABEL[ev.event_key] ?? ev.event_key;
  // 3. 舊 doc_type（backward compat）
  if (ev.doc_type) return _DOC_TYPE_LABEL[ev.doc_type] ?? ev.doc_type;
  // 4. stub source_id 格式：stub-{ticker}-{period}-{doctype}
  const m = ev.source_id.match(/^stub-\d+-\w+-(\w+)$/);
  if (m) return _DOC_TYPE_LABEL[m[1]] ?? m[1];
  // 5. origin fallback
  return _ORIGIN_LABEL[ev.origin] ?? "文件";
}

// 每個 trace step 展開成 THINK / ACT / OBS 三格（空字串的格跳過）
function expandTraceStep(step: ResearchTraceStepRaw): TraceStepVM[] {
  const items: TraceStepVM[] = [];
  if (step.thought)
    items.push({ type: "THINK", text: step.thought, tool: false });
  if (step.action && step.action !== "finish") {
    const call = step.action_input
      ? `${step.action}("${step.action_input}")`
      : step.action;
    items.push({ type: "ACT", text: call, tool: true });
  }
  if (step.observation)
    items.push({ type: "OBS", text: step.observation, tool: false });
  return items;
}

// LLM markdown 清理：去掉列表標記（- / * / 1.）和粗體標記（**...**）
function stripMarkdown(line: string): string {
  return line
    .replace(/^[\-\*]\s+/, "")
    .replace(/^\d+\.\s+/, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/`(.*?)`/g, "$1")
    .trim();
}

// final_answer 切成摘要條列：只按換行切，保留 LLM 段落結構
// 不再用句號強切，以免把一段連續論述拆成假條列
function splitAnswer(text: string): string[] {
  const lines = text
    .split(/\n+/)
    .map(stripMarkdown)
    .filter(Boolean);
  return lines.length > 0 ? lines : [text.trim()].filter(Boolean);
}

export function normalizeResearch(raw: ResearchResponse, query: string): AskVM {
  const finishInput = raw.react_steps.slice().reverse()
    .find((s) => s.action === "finish" && s.action_input)?.action_input;
  const answerText = finishInput || raw.final_answer || "";
  const bullets = splitAnswer(answerText);
  const summary: SummaryItemVM[] = bullets.map((text, i) => {
    const ev = findInlineCitation(text, raw.evidence) ?? raw.evidence[i];
    return {
      text,
      cite: ev?.source_id ?? "",
      page: "",
      doc_type_label: ev ? citationLabel(ev) : undefined,
    };
  });

  const citations: CitationTrackerVM[] = raw.evidence.map((ev, i) => ({
    ix:      String(i + 1),
    label:   ev.company ? `${ev.company} · ${citationLabel(ev)}` : citationLabel(ev),
    detail:  ev.published_yyyymm
               ? String(ev.published_yyyymm).replace(/^(\d{4})(\d{2})$/, "$1-$2")
               : (ev.published_at ?? (ev.snippet.length > 60 ? ev.snippet.slice(0, 60) + "…" : ev.snippet)),
    cite:    ev.source_id,
    snippet: ev.snippet,
    period:  ev.published_yyyymm
               ? String(ev.published_yyyymm).replace(/^(\d{4})(\d{2})$/, "$1-$2")
               : (ev.fiscal_period ?? ""),
  }));

  const react: TraceStepVM[] = raw.react_steps.flatMap(expandTraceStep);
  const retrieval_degraded =
    raw.evidence.length === 0 ||
    raw.evidence.every((ev) => ev.origin === "bm25" || ev.origin === "stub");

  return { query, compliance_status: raw.compliance_status, retrieval_degraded, kpis: [], summary, chart: [], react, citations };
}
