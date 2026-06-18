// ============================================================
// lib/adapters.ts — 後端形狀 → View-Model 正規化（唯一轉換層）
// 元件不直接碰後端形狀，只讀 VM。
// ============================================================
import type {
  AlertRaw, Severity, KpiRaw, SummaryItemRaw, ChartPointRaw,
  ReactStepRaw, AskResponse, CompanyRaw, CompanyResponse,
  NewsItemRaw, NewsResponse, DocRaw, LibraryResponse,
  HistoryItemRaw, NotificationItemRaw, NotificationsResponse,
  ResolveResponse, WatchItemRaw, GroundedValue, CitationRaw,
  ResearchResponse, ResearchCitationRaw, ResearchReActStepRaw,
} from "@/types/api";
import type {
  AlertVM, AlertLevel, KpiVM, SummaryItemVM, ChartPointVM,
  ReActStepVM, AskVM, CompanyVM, ComparisonVM, NewsItemVM, NewsVM,
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
    origin: "research",  // watchdog alerts 顯示於所有面板，filter 已移至 pages
    level: sevToLevel(raw.severity),
    title: raw.ticker ? `${raw.ticker} · MOPS 監控` : "系統警示",
    summary: raw.summary,
    source: raw.ticker ?? "MOPS Watchdog",
    time: "",
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

function mapTraceToReact(steps: ReactStepRaw[]): ReActStepVM[] {
  return steps.map((s) => ({ type: s.type, text: s.text, tool: s.tool }));
}

export function normalizeAsk(raw: AskResponse): AskVM {
  return {
    query: raw.query,
    kpis: raw.kpis.map(normalizeKpi),
    summary: raw.summary.map(normalizeSummaryItem),
    chart: raw.chart,
    react: mapTraceToReact(raw.react_steps),
    citations: raw.citations.map((c, i) => ({
      ix: String(i + 1),
      label: c.src,
      detail: c.page,
      cite: c.src,
      snippet: "",
      period: "",
    })),
  };
}

export function normalizeCompany(raw: CompanyRaw): CompanyVM {
  return {
    id: raw.ticker,
    name: raw.company_name ?? raw.ticker,
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

// origin（搜尋方法）→ 中文 fallback，當 doc_type 不存在時用
const _ORIGIN_LABEL: Record<ResearchCitationRaw["origin"], string> = {
  stub:      "文件",
  bm25:      "文件",
  embedding: "文件",
  rerank:    "文件",
  colpali:   "法說簡報",
  news:      "新聞",
};

function citationLabel(ev: ResearchCitationRaw): string {
  // 1. 後端直接帶 doc_type（真實 BQ 資料）
  if (ev.doc_type) return _DOC_TYPE_LABEL[ev.doc_type] ?? ev.doc_type;
  // 2. stub source_id 格式：stub-{ticker}-{period}-{doctype}
  const m = ev.source_id.match(/^stub-\d+-\w+-(\w+)$/);
  if (m) return _DOC_TYPE_LABEL[m[1]] ?? m[1];
  // 3. origin fallback
  return _ORIGIN_LABEL[ev.origin] ?? "文件";
}

// 每個 ReActStep 展開成 THINK / ACT / OBS 三格（空字串的格跳過）
function expandReActStep(step: ResearchReActStepRaw): ReActStepVM[] {
  const items: ReActStepVM[] = [];
  if (step.thought)
    items.push({ type: "THINK", text: step.thought, tool: false });
  if (step.action) {
    const call = step.action_input
      ? `${step.action}("${step.action_input}")`
      : step.action;
    items.push({ type: "ACT", text: call, tool: true });
  }
  if (step.observation)
    items.push({ type: "OBS", text: step.observation, tool: false });
  return items;
}

// final_answer 切成摘要條列：先嘗試換行符，不夠再用句號
function splitAnswer(text: string): string[] {
  const byLine = text.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  if (byLine.length > 1) return byLine;
  return text.split(/(?<=。)/).map((s) => s.trim()).filter(Boolean);
}

export function normalizeResearch(raw: ResearchResponse, query: string): AskVM {
  const bullets = splitAnswer(raw.final_answer);
  const summary: SummaryItemVM[] = bullets.map((text, i) => ({
    text,
    cite: raw.evidence[i]?.source_id ?? raw.evidence[0]?.source_id ?? "",
    page: "",
  }));

  const citations: CitationTrackerVM[] = raw.evidence.map((ev, i) => ({
    ix:      String(i + 1),
    label:   citationLabel(ev),
    detail:  ev.published_at ?? (ev.snippet.length > 60 ? ev.snippet.slice(0, 60) + "…" : ev.snippet),
    cite:    ev.source_id,
    snippet: ev.snippet,
    period:  ev.fiscal_period ?? "",
  }));

  const react: ReActStepVM[] = raw.react_steps.flatMap(expandReActStep);

  return { query, kpis: [], summary, chart: [], react, citations };
}
