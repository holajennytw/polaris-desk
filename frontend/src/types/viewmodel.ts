// ============================================================
// types/viewmodel.ts — 前端 View-Model 合約（已正規化）
// 元件只吃這些形狀，後端原始形狀在 types/api.ts，轉換在 lib/adapters.ts
// ============================================================

export type AlertLevel = "high" | "mid" | "info";

export interface AlertVM {
  id: string;
  origin: "research" | "peer" | "contradiction";
  level: AlertLevel;
  title: string;
  summary: string;
  source: string;
  time: string;
  stock?: string;
}

export interface CitationVM {
  src: string;
  page: string;
}

export type GroundedVM =
  | string
  | { v: string; citations: CitationVM[] };

export interface KpiVM {
  label: string;
  value: string;
  unit: string;
  delta: string;
  trend: "up" | "down";
  cite: string;
}

export interface SummaryItemVM {
  text: string;
  cite: string;
  page: string;
  doc_type_label?: string; // 重大訊息 / 法說逐字稿 / 新聞 — 顯示用，非 source_id
}

export interface ChartPointVM {
  label: string;
  value: number;
}

export interface ReActStepVM {
  type: "THINK" | "ACT" | "OBS";
  text: string;
  tool: boolean;
}

export interface CitationTrackerVM {
  ix: string;
  label: string;
  detail: string;
  cite: string;
  snippet: string;
  period: string;
}

export interface AskVM {
  query: string;
  compliance_status: string;
  kpis: KpiVM[];
  summary: SummaryItemVM[];
  chart: ChartPointVM[];
  react: ReActStepVM[];
  citations: CitationTrackerVM[];
}

export interface CompanyVM {
  id: string;
  name: string;
  provenance: "real" | "mock";
}

export interface PeerKpiVM {
  label: string;
  a: GroundedVM;
  b: GroundedVM;
  diff: string;
  better: "a" | "b";
}

export interface PnlRowVM {
  metric: string;
  a: GroundedVM;
  b: GroundedVM;
  note: string;
}

export interface MixRowVM {
  label: string;
  a: number;
  b: number;
}

export interface CallRowVM {
  dim: string;
  topic: string;
  a: { stance: string; tone: "pos" | "neu" | "neg"; quote: string; cite: string };
  b: { stance: string; tone: "pos" | "neu" | "neg"; quote: string; cite: string };
}

export interface EventVM {
  date: string;
  side: "a" | "b";
  level: "high" | "mid" | "low";
  title: string;
}

export interface TopicVM {
  label: string;
  a: number;
  b: number;
}

export interface ValuationRowVM {
  metric: string;
  a: string;
  b: string;
  note: string;
}

export interface ComparisonVM {
  meta: { provenance: string; trust: string; note: string };
  kpis: PeerKpiVM[];
  financial: {
    pnl: PnlRowVM[];
    mix: { label: string; note: string; rows: MixRowVM[] };
  };
  calls: {
    period: string;
    rows: CallRowVM[];
  };
  news: {
    window: string;
    senti: { a: { pos: number; neu: number; neg: number }; b: { pos: number; neu: number; neg: number } };
    events: EventVM[];
    topics: TopicVM[];
  };
  valuation: {
    asof: string;
    multiple: ValuationRowVM[];
    payout: ValuationRowVM[];
  };
}

export interface NewsItemVM {
  id: string;
  cite: string;
  title: string;
  summary: string;
  time: string;
  tags: string[];
  url?: string;
}

export interface NewsVM {
  updated: string;
  tabs: Array<{ id: string; label: string; count: number }>;
  items: NewsItemVM[];
}

/** BQ-aligned doc view-model（R4 API 接通前部分欄位為 mock 值） */
export interface DocVM {
  id: string;
  ticker: string;
  company_name: string;
  doc_type: string;     // major_news | transcript | earnings_call | news
  fiscal_period: string;
  source_file: string;
  page_count: number;
  published_at: string;
  fetched_at: string;
  ingested: boolean;
}

export interface LibraryVM {
  stats: Array<{ label: string; value: string }>;
  types: Array<{ id: string; label: string; count: number }>;
  docs: DocVM[];
}

export interface HistoryItemVM {
  id: string;
  query: string;
  page: string;
  time: string;
  tags: string[];
}

export interface NotificationItemVM {
  id: string;
  type: "risk" | "tracking" | "system";
  title: string;
  body: string;
  time: string;
  read: boolean;
}

export interface NotificationsVM {
  items: NotificationItemVM[];
  unread: number;
}

export interface ResolveVM {
  ordered: Array<{ id: string; name: string; status: "ok" | "nodata" }>;
  period: string;
  tab: string;
}

export interface WatchItemVM {
  id: string;
  stock: string;
  name: string;
  trigger: string;
  status: "active" | "paused";
  lastTriggered?: string;
}
