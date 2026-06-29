// ============================================================
// types/api.ts — 後端 API 原始回傳形狀（raw shapes）
// 只描述結構，不含前端邏輯。
// ============================================================

// ── 共用基礎型別 ─────────────────────────────────────────────

export type Severity = "alert" | "watch" | "info";

export interface CitationRaw {
  src: string;
  page: string;
}

export type GroundedValue =
  | string
  | { v: string; citations: CitationRaw[] };

export interface KpiRaw {
  label: string;
  value: string;
  unit: string;
  delta: string;
  trend: "up" | "down";
  cite_key: string;
}

export interface SummaryItemRaw {
  text: string;
  cite_key: string;
  page: string;
}

export interface ChartPointRaw {
  label: string;
  value: number;
}

export interface ReactStepRaw {
  type: "THINK" | "ACT" | "OBS";
  text: string;
  tool: boolean;
}

// ── 公司清單 GET /companies ───────────────────────────────────

export interface CompanyRaw {
  ticker: string;
  company_name: string | null;
  english_name: string | null;
  market: string | null;
  industry_id: string | null;
  industry_name: string | null;
  is_financial: boolean | null;
  aliases: string | null;
}

// ── 研究助理 ─────────────────────────────────────────────────
// POST /ask

export interface AskCitationRaw {
  source_id: string;
  snippet: string;
  origin: CitationOrigin;
  company: string | null;
}

export interface NodeTraceRaw {
  node_name: string;
  status: "ok" | "error" | "skipped";
  input_keys: string[];
  output_keys: string[];
  error_message: string | null;
  elapsed_ms: number;
}

export interface AskResponse {
  answer: string;
  compliance_status: string;
  citations: AskCitationRaw[];
  trace: NodeTraceRaw[];
}

// POST /research

export type CitationOrigin = "stub" | "bm25" | "embedding" | "colpali" | "rerank" | "news" | "vision";

/** @deprecated 改用 CitationOrigin */
export type ResearchCitationOrigin = CitationOrigin;

export interface ResearchCitationRaw {
  source_id: string;
  snippet: string;
  origin: CitationOrigin;
  company?: string;
  event_key?: string;
  source_key?: string;
  published_yyyymm?: number;
  // legacy（stub / BM25 仍可能出現）
  doc_type?: string;
  published_at?: string;
  fiscal_period?: string;
}

export interface ResearchTraceStepRaw {
  thought: string;
  action: string;
  action_input: string;
  observation: string;
}

export interface ResearchResponse {
  final_answer: string;
  evidence: ResearchCitationRaw[];
  react_steps: ResearchTraceStepRaw[];
  status: string;
  compliance_status: string;
}

// GET /chunk/{source_id}

export interface ChunkRaw {
  source_id: string;
  title: string;
  doc_type: string;
  kind_label: string;
  ticker: string;
  fiscal_period: string;
  published_at: string;
  page: string | null;
  trust: "high" | "mid";
  content: string;
  highlight: string;
  hl_tokens?: string[];
}

// ── 同業比較 POST /peer-compare ──────────────────────────────

export interface PeerKpiRaw {
  label: string;
  a: GroundedValue;
  b: GroundedValue;
  diff: string;
  better: "a" | "b";
}

export interface PnlRowRaw {
  metric: string;
  a: GroundedValue;
  b: GroundedValue;
  note: string;
}

export interface MixRowRaw {
  label: string;
  a: number;
  b: number;
}

export interface CallRowRaw {
  dim: string;
  topic: string;
  a: { stance: string; tone: "pos" | "neu" | "neg"; quote: string; cite: string };
  b: { stance: string; tone: "pos" | "neu" | "neg"; quote: string; cite: string };
}

export interface EventRaw {
  date: string;
  side: "a" | "b";
  level: "high" | "mid" | "low";
  title: string;
}

export interface TopicRaw {
  label: string;
  a: number;
  b: number;
}

export interface ValuationRowRaw {
  metric: string;
  a: string;
  b: string;
  note: string;
}

export interface PeerCompareTrendPoint {
  period: string;
  metric: string;
  a_value: number | null;
  b_value: number | null;
}

// 後端實際回傳形狀（src/polaris/api.py PeerCompareResponse）
// 欄位名與 FastAPI Pydantic model 一字不差。

export interface BackendPeerCitationRaw {
  src: string;
  page: string;  // fiscal_period 字串，非 snippet
}

export interface BackendPeerKpiSide {
  v: string;
  citations: BackendPeerCitationRaw[];
}

export interface BackendPeerKpiRaw {
  label: string;  // 已做 metric_id → 中文 label 轉換
  a: BackendPeerKpiSide;
  b: BackendPeerKpiSide;
  diff: string;
  better: "a" | "b";
}

export interface BackendPeerFinancialRow {
  metric: string;
  a: BackendPeerKpiSide;
  b: BackendPeerKpiSide;
  better: "a" | "b";
  note: string;
}

export interface BackendPeerCallSide {
  stance: string;
  tone: "pos" | "neu" | "neg";
  quote: string;
  cite: string;
}

export interface BackendPeerCallRaw {
  dim: string;
  topic: string;
  a: BackendPeerCallSide;
  b: BackendPeerCallSide;
}

export interface BackendPeerCompareResponse {
  a_ticker:          string;
  b_ticker:          string;
  fiscal_period:     string;
  kpis:              BackendPeerKpiRaw[];
  financial:         BackendPeerFinancialRow[];
  calls:             BackendPeerCallRaw[];
  calls_period?:     string | null;  // 法說退回時的實際來源季（≠ fiscal_period）；否則 null
  trend:             PeerCompareTrendPoint[];
  valuation:         unknown[];
  summary:           string;
  compliance_status: string;
}

// 前端正規化後形狀（給 peer/page.tsx 使用，與 peer-result.ts PeerResultLike 對齊）
// 與後端形狀基本一致，normalizePeerCompare 做型別驗證與 pass-through。

export interface PeerCitationNorm {
  src: string;
  page: string;
}

export interface PeerKpiNorm {
  label: string;
  a: { v: string; citations: PeerCitationNorm[] };
  b: { v: string; citations: PeerCitationNorm[] };
  diff: string;
  better: string;
}

export interface PeerCallNorm {
  dim: string;
  topic: string;
  a: { stance: string; tone: string; quote: string; cite: string };
  b: { stance: string; tone: string; quote: string; cite: string };
}

export interface PeerFinancialNorm {
  metric: string;
  a: { v: string; citations: PeerCitationNorm[] };
  b: { v: string; citations: PeerCitationNorm[] };
  better: "a" | "b";
  note: string;
}

export interface PeerCompareResult {
  a_ticker:          string;
  b_ticker:          string;
  fiscal_period:     string;
  kpis:              PeerKpiNorm[];
  financial:         PeerFinancialNorm[];
  calls:             PeerCallNorm[];
  calls_period:      string | null;  // 法說退回時的實際來源季（≠ fiscal_period）；否則 null
  trend:             PeerCompareTrendPoint[];
  valuation:         unknown[];
  summary:           string;
  compliance_status: string;
}

// 舊版（mock/company endpoint 形狀，保留給 /company/:id 使用）
export interface PeerCompareResponse {
  a_ticker:         string;
  b_ticker:         string;
  fiscal_period:    string;
  kpis:             PeerKpiRaw[];
  financial:        PnlRowRaw[];
  calls:            CallRowRaw[];
  valuation:        ValuationRowRaw[];
  trend:            PeerCompareTrendPoint[];
  summary:          string;
  compliance_status: string;
}

export interface CompanyResponse {
  id: string;
  name: string;
  provenance: "real" | "mock";
  kpis: PeerKpiRaw[];
  financial: {
    pnl: PnlRowRaw[];
    mix: { label: string; note: string; rows: MixRowRaw[] };
  };
  calls: {
    period: string;
    rows: CallRowRaw[];
  };
  news: {
    window: string;
    senti: { a: { pos: number; neu: number; neg: number }; b: { pos: number; neu: number; neg: number } };
    events: EventRaw[];
    topics: TopicRaw[];
  };
  valuation: {
    asof: string;
    multiple: ValuationRowRaw[];
    payout: ValuationRowRaw[];
  };
}

// ── 警示 GET /alerts ──────────────────────────────────────────

export interface AlertRaw {
  event_id: string;
  ticker: string;
  summary: string;
  compliance_status: string;
  severity: Severity;
  evidence: Array<{
    source_id: string;
    snippet: string;
    origin: string;
    company: string | null;
  }>;
  title?: string;
  time?: string;
  source?: string;
  origin?: string;
}

// ── 矛盾偵測 POST /contradiction ──────────────────────────────

export interface ContradictionResponse {
  alerts: AlertRaw[];
}

// ── 提示晶片 GET /suggestions ─────────────────────────────────

export interface SuggestionsResponse {
  suggestions: string[];
  source: "rule" | "llm";
  is_generating: boolean;
}

// ── 新聞 GET /news ────────────────────────────────────────────

export interface NewsItemRaw {
  id: string;
  source_key: string;
  title: string;
  summary: string;
  time: string;
  tags: string[];
  url?: string;
}

export interface NewsTab {
  id: string;
  label: string;
  count: number;
}

export interface NewsResponse {
  updated: string;
  tabs: NewsTab[];
  items: NewsItemRaw[];
}

// ── 文件庫 GET /library ───────────────────────────────────────

/** BQ-aligned: colpali_pages × company_dim JOIN（R4 API 接通前為 mock） */
export interface DocRaw {
  id: string;           // page_id 或複合 key
  ticker: string;       // BQ join key
  company_name: string; // company_dim.company_name
  doc_type: string;     // major_news | transcript | earnings_call | news
  fiscal_period: string; // 如 2025Q4
  source_file: string;  // 原始檔名
  page_count: number;   // colpali_pages 中該文件的頁數
  published_at: string; // ISO date
  fetched_at: string;   // 抓取日 ISO date
  ingested: boolean;    // 是否已建 chunks 索引
  // 向下相容舊 mock 欄位（接通 BQ API 後移除）
  title?: string;
  kind?: string;
  company?: string;
  period?: string;
  pages?: number;
  size?: string;
  time?: string;
  tags?: string[];
}

export interface LibraryStats {
  label: string;
  value: string;
}

export interface LibraryResponse {
  stats: LibraryStats[];
  types: { id: string; label: string; count: number }[];
  docs: DocRaw[];
}

// ── 財務指標 GET /financials ──────────────────────────────────

export interface FinancialRow {
  ticker: string;
  fiscal_period: string | null;
  metric_id: string | null;
  metric_name: string | null;
  value: number | null;
  unit: string | null;
  source_id: string | null;
  published_at: string | null;
  year: number | null;
  month: number | null;
}

// ── 歷史 / 通知 / 監看 ───────────────────────────────────────

export interface HistoryItemRaw {
  id: string;
  query: string;
  page: string;
  time: string;
  tags: string[];
}

export interface NotificationItemRaw {
  id: string;
  type: "risk" | "tracking" | "system";
  title: string;
  body: string;
  time: string;
  read: boolean;
}

export interface NotificationsResponse {
  items: NotificationItemRaw[];
  unread_count: number;
  delivery_failures?: string[];
}

export interface ResolveResponse {
  ordered: Array<{ id: string; name: string; status: "ok" | "nodata" }>;
  period: string;
  tab: string;
}

export interface WatchItemRaw {
  id: string;
  stock_id: string;
  name: string;
  trigger: string;
  status: "active" | "paused";
  last_triggered?: string;
}
