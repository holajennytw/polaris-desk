"use client";
import { useState, useRef, useEffect } from "react";
import { mutate } from "swr";
import { historyStore } from "@/lib/historyStore";
import { api } from "@/lib/api";
import { Icon } from "@/components/ui/Icon";
import { AlertItem } from "@/components/polaris/AlertItem";
import { ReActTrace } from "@/components/polaris/ReActTrace";
import { ComplianceBanner } from "@/components/polaris/ComplianceBanner";
import { DocViewer, type DocContent } from "@/components/polaris/DocViewer";
import { ReportModal } from "@/components/polaris/ReportModal";
import { useReadStore } from "@/hooks/useReadStore";
import { useCompanies } from "@/hooks/useCompanies";
import { useContraAlerts } from "@/hooks/useContraAlerts";
import { useSuggestions } from "@/hooks/useSuggestions";
import { toast } from "sonner";
import { contraAlertStore, type ContraAlert } from "@/lib/contraAlertStore";
import { parseQuery } from "@/lib/peer";
import { useFinancials, type FinancialRow } from "@/hooks/useFinancials";
import type { ReActStepVM, CompanyVM, KpiVM, SummaryItemVM } from "@/types/viewmodel";

const PEER_TABS = [
  { id:"financial", label:"財務" }, { id:"calls", label:"法說會" },
  { id:"news", label:"新聞" }, { id:"valuation", label:"估值" },
];
const PRESETS = [
  "比較台積電與聯發科毛利率",
  "台積電 vs 鴻海 法說會重點",
  "聯發科與聯詠估值比較",
];
const PHASES = ["解析查詢意圖","檢索 A 公司文件","檢索 B 公司文件","交叉比對指標","生成比較摘要","合規檢查"];
const PERIOD_OPTIONS = ["2026Q1","2025Q4","2025Q3","2025Q2","2025Q1","2024Q4"];
const MOCK_REACT: ReActStepVM[] = [
  { type:"THINK", text:"解析兩間公司比較意圖，規劃：分別取法說稿與財報交叉驗證。", tool:false },
  { type:"ACT",   text:'retriever.search("A 公司 法說會 財報")', tool:true },
  { type:"OBS",   text:"取得 A 公司相關引用，最高相關 stub 文件。", tool:false },
  { type:"ACT",   text:'retriever.search("B 公司 法說會 財報")', tool:true },
  { type:"OBS",   text:"取得 B 公司相關引用，來源可溯源。", tool:false },
  { type:"THINK", text:"交叉比對兩公司關鍵指標，確認數據口徑一致。", tool:false },
  { type:"ACT",   text:"compliance_check(comparison_output)", tool:true },
  { type:"OBS",   text:"passed — 以下為事實對比，非投資建議。", tool:false },
];

function buildMockPeerContradictions(aName: string, bName: string): ContraAlert[] {
  const now = new Date().toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
  return [{
    id: `peer-contra-pass-${Date.now()}`,
    origin: "contradiction",
    level: "info",
    title: "同業交叉比對通過",
    summary: `${aName} 與 ${bName} 各引用來源數字交叉比對完成，未發現明顯矛盾。`,
    source: "矛盾偵測引擎 · 同業比較",
    time: now,
  }];
}

function buildPeerReportKpis(aName: string, bName: string): KpiVM[] {
  return [
    { label:`${aName} 毛利率`,     value:"57.8", unit:"%", delta:`領先 ${bName} +19.5pp`, trend:"up",   cite:"" },
    { label:`${bName} 毛利率`,     value:"38.3", unit:"%", delta:"",                       trend:"down", cite:"" },
    { label:`${aName} 營業利益率`, value:"47.5", unit:"%", delta:`領先 ${bName} +27.4pp`, trend:"up",   cite:"" },
    { label:`${bName} 營業利益率`, value:"20.1", unit:"%", delta:"",                       trend:"down", cite:"" },
    { label:`${aName} 營收 YoY`,   value:"+39",  unit:"%", delta:`領先 ${bName} +22pp`,   trend:"up",   cite:"" },
    { label:`${bName} 營收 YoY`,   value:"+17",  unit:"%", delta:"",                       trend:"down", cite:"" },
  ];
}

function buildPeerReportSummary(aName: string, bName: string): SummaryItemVM[] {
  return [
    { text:`${aName} 毛利率 57.8%，較 ${bName}（38.3%）高出 19.5pp。`, cite:"", page:"" },
    { text:`${aName} 營業利益率 47.5%，較 ${bName}（20.1%）高出 27.4pp。`, cite:"", page:"" },
    { text:`${aName} 營收 YoY +39%，成長動能優於 ${bName}（+17%）。`, cite:"", page:"" },
    { text:"本比較為事實對比，非投資建議；數據待後端接入後自動更新。", cite:"", page:"" },
  ];
}

// ── Trend Panel ──────────────────────────────────────────────

function TrendPanel({ aName, bName }: { aName: string; bName: string }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">
          <Icon name="arrowUp" size={15} style={{ color: "rgb(var(--primary))", verticalAlign: "-3px", marginRight: 6 }}/>
          毛利率趨勢對比
        </span>
        <span className="panel-meta">待接後端</span>
      </div>
      <div className="chart-empty" style={{ padding: "28px 16px" }}>
        <span>{aName} vs {bName} · 近 6 季趨勢，等 R3 交付 POST /peer-compare trend 欄位後顯示</span>
      </div>
    </div>
  );
}

// ── Peer Summary Panel ────────────────────────────────────────

function PeerSummaryPanel({ aName, bName }: { aName: string; bName: string }) {
  const items = buildPeerReportSummary(aName, bName);
  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">
          <Icon name="layers" size={15} style={{ color: "rgb(var(--primary))", verticalAlign: "-3px", marginRight: 6 }}/>
          比較摘要
        </span>
        <span className="panel-meta">待接後端</span>
      </div>
      <div className="panel-body">
        <ul className="summary">
          {items.map((s, i) => (
            <li key={i}>
              <span className="sum-marker"/>
              <span>{s.text}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// ── Comparison blocks ─────────────────────────────────────────

function getLatestMetric(rows: FinancialRow[], metricId: string): number | null {
  if (!rows.length) return null;
  const periods = [...new Set(rows.map(r => r.fiscal_period).filter(Boolean))].sort() as string[];
  const latestPeriod = periods.at(-1);
  return rows.find(r => r.fiscal_period === latestPeriod && r.metric_id === metricId)?.value ?? null;
}

function getLatestYoy(rows: FinancialRow[]): number | null {
  return getLatestMetric(rows, "revenue_yoy");
}

function fmtYoy(v: number | null): string {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function fmtRevenue(v: number | null): string {
  if (v === null) return "—";
  const yi = v / 100_000; // 千元 → 億元
  return `${yi >= 100 ? yi.toFixed(0) : yi.toFixed(1)}億`;
}

function PeerKpiGrid({ aName, bName, aTicker, bTicker }: {
  aName: string; bName: string; aTicker: string; bTicker: string;
}) {
  const { rows: aRows } = useFinancials(aTicker || null);
  const { rows: bRows } = useFinancials(bTicker || null);

  const aRevenue = getLatestMetric(aRows, "revenue");
  const bRevenue = getLatestMetric(bRows, "revenue");
  const aYoy     = getLatestYoy(aRows);
  const bYoy     = getLatestYoy(bRows);

  const revDiff = (aRevenue !== null && bRevenue !== null)
    ? `${(aRevenue - bRevenue) >= 0 ? "+" : ""}${((aRevenue - bRevenue) / 100_000).toFixed(0)}億`
    : "—";
  const revBetter  = (aRevenue !== null && bRevenue !== null) ? (aRevenue >= bRevenue ? "a" : "b") : "";
  const yoyDiff    = (aYoy !== null && bYoy !== null)
    ? `${(aYoy - bYoy) >= 0 ? "+" : ""}${(aYoy - bYoy).toFixed(1)}pp`
    : "—";
  const yoyBetter  = (aYoy !== null && bYoy !== null) ? (aYoy >= bYoy ? "a" : "b") : "";

  const kpis = [
    { label:"月營收",      a:fmtRevenue(aRevenue), b:fmtRevenue(bRevenue), diff:revDiff,    better:revBetter },
    { label:"月營收 YoY",  a:fmtYoy(aYoy),         b:fmtYoy(bYoy),         diff:yoyDiff,    better:yoyBetter },
    { label:"毛利率",      a:"—",                   b:"—",                  diff:"待接後端",  better:"" },
    { label:"營業利益率",  a:"—",                   b:"—",                  diff:"待接後端",  better:"" },
  ];
  return (
    <div className="peer-kpi-grid">
      {kpis.map((k,i) => (
        <div className="peer-kpi card" key={i}>
          <div className="pk-label">{k.label}</div>
          <div className="pk-row">
            <div className="pk-side"><div className="pk-name">{aName}</div><div className={"pk-val font-display"+(k.better==="a"?" win":"")}>{k.a}</div></div>
            <div className="pk-side"><div className="pk-name">{bName}</div><div className={"pk-val font-display"+(k.better==="b"?" win":"")}>{k.b}</div></div>
          </div>
          <div className="pk-diff"><Icon name="arrowUp" size={13}/>{k.better==="a"?aName:bName}領先 {k.diff}</div>
        </div>
      ))}
    </div>
  );
}

function FinancialBlock({ aName, bName }: { aName:string; bName:string }) {
  const rows = [
    { metric:"營收",     a:"23.5", b:"—", note:"" },
    { metric:"毛利率",   a:"57.8%", b:"—", note:"" },
    { metric:"營業利益率", a:"47.5%", b:"—", note:"" },
    { metric:"研發費用率", a:"7.8%",  b:"—", note:"" },
    { metric:"資本支出", a:"6.4", b:"—", note:"" },
  ];
  return (
    <div className="panel">
      <div className="panel-head"><span className="panel-title">損益指標對比</span><span className="panel-meta">待接後端</span></div>
      <div className="panel-body">
        <table className="ptable">
          <thead><tr><th>指標</th><th>{aName}</th><th>{bName}</th><th>備註</th></tr></thead>
          <tbody>{rows.map((r,i) => <tr key={i}><td>{r.metric}</td><td><b>{r.a}</b></td><td>{r.b}</td><td style={{color:"rgb(var(--muted))",fontSize:13}}>{r.note}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

function CallsBlock({ aName, bName, onOpen }: { aName:string; bName:string; onOpen:(doc:DocContent)=>void }) {
  const rows = [
    { topic:"AI / HPC 需求", aStance:"強勁", aTone:"pos", aQuote:"AI 與伺服器需求帶動成長。", aSourceId:"", bStance:"—", bTone:"neu", bQuote:"待接後端", bSourceId:"" },
    { topic:"資本支出",      aStance:"高檔", aTone:"neu", aQuote:"全年資本支出維持高檔。",    aSourceId:"", bStance:"—", bTone:"neu", bQuote:"待接後端", bSourceId:"" },
    { topic:"毛利展望",      aStance:"走升", aTone:"pos", aQuote:"良率改善，毛利率季增。",    aSourceId:"", bStance:"—", bTone:"neu", bQuote:"待接後端", bSourceId:"" },
  ];
  const openQuote = async (name: string, quote: string, sourceId: string) => {
    if (!sourceId) return;
    const chunk = await api.chunk(sourceId);
    if (chunk) { onOpen(chunk); return; }
    onOpen({ key: sourceId, title: `${name} 法說逐字稿`, kind: "transcript", source_id: sourceId, page: "", trust: "mid", highlight: quote, body: [quote] });
  };
  return (
    <div className="panel">
      <div className="panel-head"><span className="panel-title">法說會</span><span className="panel-meta">待接後端</span></div>
      <div className="panel-body">
        <div className="cmatrix">
          <div className="cm-head"><span>主題</span><span>{aName}</span><span>{bName}</span></div>
          {rows.map((r,i) => (
            <div key={i} className="cm-row">
              <div className="cm-topic">{r.topic}</div>
              <div className="cm-cell">
                <span className={"tag "+r.aTone}>{r.aStance}</span>
                <div className="cm-quote">
                  {r.aQuote}
                  {r.aSourceId && <button className="cm-cite-btn" onClick={() => openQuote(aName, r.aQuote, r.aSourceId)}><Icon name="quote" size={11}/>查看</button>}
                </div>
              </div>
              <div className="cm-cell">
                <span className={"tag "+r.bTone}>{r.bStance}</span>
                <div className="cm-quote">
                  {r.bQuote}
                  {r.bSourceId && <button className="cm-cite-btn" onClick={() => openQuote(bName, r.bQuote, r.bSourceId)}><Icon name="quote" size={11}/>查看</button>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function NewsBlock({ aName, bName }: { aName:string; bName:string }) {
  return (
    <div className="panel">
      <div className="panel-head"><span className="panel-title">新聞</span><span className="panel-meta">待接後端</span></div>
      <div className="panel-body">
        <div style={{display:"flex",gap:24,flexWrap:"wrap"}}>
          {[aName, bName].map((name,i) => (
            <div key={i} style={{flex:1,minWidth:180}}>
              <div style={{fontWeight:600,marginBottom:8}}>{name}</div>
              <div className="chart-empty" style={{padding:"16px 16px"}}><span>情緒數據待接後端</span></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ValuationBlock({ aName, bName }: { aName:string; bName:string }) {
  const rows = [
    { metric:"本益比 PE",    a:"—", b:"—", note:"" },
    { metric:"股價淨值比 PB", a:"—", b:"—", note:"" },
    { metric:"EV / EBITDA",  a:"—", b:"—", note:"" },
    { metric:"ROE",          a:"—", b:"—", note:"" },
  ];
  return (
    <div className="panel">
      <div className="panel-head"><span className="panel-title">估值</span><span className="panel-meta">待接後端</span></div>
      <div className="panel-body">
        <table className="ptable">
          <thead><tr><th>指標</th><th>{aName}</th><th>{bName}</th><th>備註</th></tr></thead>
          <tbody>{rows.map((r,i) => <tr key={i}><td>{r.metric}</td><td>{r.a}</td><td>{r.b}</td><td style={{color:"rgb(var(--muted))",fontSize:13}}>{r.note}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Company Slot ──────────────────────────────────────────────

interface SlotProps {
  company: CompanyVM | undefined;
  open: boolean;
  search: string;
  options: CompanyVM[];
  placeholder: string;
  onToggle: () => void;
  onSearch: (v: string) => void;
  onSelect: (id: string) => void;
}
function CompanySlot({ company, open, search, options, placeholder, onToggle, onSearch, onSelect }: SlotProps) {

  const filtered = options.filter(c => (c.name ?? "").includes(search) || c.id.includes(search));
  return (
    <div className="cpick-wrap">
      <button className={"cpick-btn"+(company ? "" : " empty")} onClick={onToggle}>
        {company?.name ?? placeholder}
        <Icon name="chevD" size={12} style={{marginLeft:5,opacity:.6}}/>
      </button>
      {open && (
        <div className="cpick-dropdown">
          <input className="cpick-search" placeholder="搜尋公司..." value={search}
            onChange={e => onSearch(e.target.value)} autoFocus/>
          {filtered.length === 0
            ? <div className="cpick-empty">無符合結果</div>
            : filtered.map(c => (
                <button key={c.id} className={"cpick-option"+(company?.id===c.id?" selected":"")}
                  onClick={() => onSelect(c.id)}>
                  <span>{c.name}</span>
                  <span className="font-mono cpick-ticker">{c.id}</span>
                </button>
              ))
          }
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────

export default function PeerPage() {
  const rs = useReadStore();
  const companies = useCompanies();
  const contraAlerts = useContraAlerts("peer");
  const { suggestions: dynamicSuggestions, fading: chipsFading } = useSuggestions({ mode: "peer" });
  const chips = dynamicSuggestions ?? PRESETS;

  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");
  const [tab, setTab] = useState("financial");
  const [fiscalPeriod, setFiscalPeriod] = useState("2026Q1");

  // 從兩間公司的財務資料推導可選季度（有資料才顯示）
  const { rows: aFinRows } = useFinancials(aId || null);
  const { rows: bFinRows } = useFinancials(bId || null);
  const availablePeriods = (() => {
    const allPeriods = [...aFinRows, ...bFinRows]
      .map(r => r.fiscal_period)
      .filter((p): p is string => !!p);
    const unique = [...new Set(allPeriods)].sort().reverse();
    return unique.length > 0 ? unique : PERIOD_OPTIONS;
  })();
  const [query, setQuery] = useState("");
  const [hasQueried, setHasQueried] = useState(false);
  const [parseMsg, setParseMsg] = useState({ ignored:[] as string[], unknown:[] as string[] });
  const [selectedAlertIdx, setSelectedAlertIdx] = useState<number|null>(null);
  const [modalAlert, setModalAlert] = useState<any>(null);
  const [openDoc, setOpenDoc] = useState<DocContent|null>(null);
  const [openSlot, setOpenSlot] = useState<"a"|"b"|null>(null);
  const [slotSearch, setSlotSearch] = useState("");
  const [phase, setPhase] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [stepN, setStepN] = useState(0);
  const [isCheckingContra, setIsCheckingContra] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [ctxOpen, setCtxOpen] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [thinkingLong, setThinkingLong] = useState(false);

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const slotRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => {
    timers.current.forEach(clearTimeout);
    if (intervalRef.current) clearInterval(intervalRef.current);
  }, []);

  useEffect(() => {
    if (phase !== "running") { setThinkingLong(false); return; }
    const t = setTimeout(() => setThinkingLong(true), 5000);
    return () => clearTimeout(t);
  }, [phase]);

  useEffect(() => {
    if (!openSlot) return;
    const handle = (e: MouseEvent) => {
      if (slotRef.current && !slotRef.current.contains(e.target as Node)) {
        setOpenSlot(null); setSlotSearch("");
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [openSlot]);

  const A = companies.find(c => c.id === aId);
  const B = companies.find(c => c.id === bId);
  const running = phase === "running";

  const startVoice = () => {
    const SR = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
    if (!SR) { alert("此瀏覽器不支援語音輸入，請改用 Chrome"); return; }
    const rec = new SR();
    rec.lang = "zh-TW";
    rec.interimResults = false;
    rec.onstart = () => setIsListening(true);
    rec.onend   = () => setIsListening(false);
    rec.onerror = () => setIsListening(false);
    rec.onresult = (e: any) => {
      const text = e.results[0][0].transcript;
      setQuery(text);
      runQuery(text);
    };
    rec.start();
  };

  const total = MOCK_REACT.length || 1;
  const curPhase = running ? PHASES[Math.min(Math.floor((stepN / total) * PHASES.length), PHASES.length - 1)] : null;

  const peerAlerts = contraAlerts.filter(a => a.level !== "info");

  const switchTab = (t: string) => setTab(t);

  const toggleSlot = (slot: "a"|"b") => { setOpenSlot(prev => prev===slot ? null : slot); setSlotSearch(""); };
  const selectCompany = (slot: "a"|"b", id: string) => {
    if (slot==="a") setAId(id); else setBId(id);
    setOpenSlot(null); setSlotSearch("");
  };

  const runContraCheck = async (aName: string, bName: string) => {
    if (isCheckingContra) return;
    setIsCheckingContra(true);
    contraAlertStore.clear("peer");
    try {
      contraAlertStore.set(buildMockPeerContradictions(aName, bName), "peer");
    } finally {
      setIsCheckingContra(false);
    }
  };

  const runQuery = async (q?: string) => {
    if (running) return;

    // 解析 query 取公司 id
    const res = parseQuery(q ?? query);
    const ok = res.ordered.filter(o => o.status === "ok");
    const nextAId = ok[0]?.id ?? aId;
    const nextBId = ok[1]?.id ?? bId;
    if (!nextAId || !nextBId) return;

    // 立即更新 company 選擇
    if (ok[0]) setAId(ok[0].id);
    if (ok[1]) setBId(ok[1].id);
    if (res.tab) switchTab(res.tab);
    const normPeriod = res.period.replace(/\s+/g, "");
    if (availablePeriods.includes(normPeriod)) setFiscalPeriod(normPeriod);
    setParseMsg({
      ignored: ok.slice(2).map(o => o.name),
      unknown: res.ordered.filter(o => o.status === "nodata").map(o => o.name),
    });

    // 解析公司名（在 setState 生效前先從 companies 讀取，避免 stale closure）
    const nextA = companies.find(c => c.id === nextAId);
    const nextB = companies.find(c => c.id === nextBId);

    timers.current.forEach(clearTimeout); timers.current = [];
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    contraAlertStore.clear("peer");
    setSelectedAlertIdx(null);
    setHasQueried(true);
    setPhase("running"); setStepN(0); setProgress(0);

    // 階段一：等待 API 期間緩慢爬升至 30%
    intervalRef.current = setInterval(() => {
      setProgress(p => Math.min(p + 2, 30));
    }, 200);

    try {
      // 模擬 API 延遲（後端 /peer-compare 接好後替換）
      await new Promise<void>(resolve => setTimeout(resolve, 1000));

      historyStore.write({ page: "peer", query: q ?? query, tags: [nextAId, nextBId].filter(Boolean) });
      api.postHistory("peer", q ?? query, [nextAId, nextBId].filter(Boolean), null);
      mutate("history");
      toast.success("已儲存至對話紀錄");

      clearInterval(intervalRef.current!); intervalRef.current = null;
      setProgress(p => Math.max(p, 30));

      // 階段二：依 MOCK_REACT 步數逐步推進至 100%
      MOCK_REACT.forEach((_, i) => {
        timers.current.push(setTimeout(() => {
          setStepN(i + 1);
          setProgress(30 + Math.round(((i + 1) / total) * 70));
        }, 220 * (i + 1)));
      });
      timers.current.push(setTimeout(() => {
        setPhase("done");
        runContraCheck(nextA?.name ?? "", nextB?.name ?? "");
      }, 220 * total + 300));

    } catch {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
      setPhase("done"); setProgress(0);
    }
  };

  const renderBlock = () => {
    const aName = A?.name ?? ""; const bName = B?.name ?? "";
    if (tab==="financial") return <FinancialBlock aName={aName} bName={bName}/>;
    if (tab==="calls")     return <CallsBlock aName={aName} bName={bName} onOpen={(doc) => setOpenDoc(doc)}/>;
    if (tab==="news")      return <NewsBlock aName={aName} bName={bName}/>;
    if (tab==="valuation") return <ValuationBlock aName={aName} bName={bName}/>;
    return null;
  };

  const readyToCompare = aId && bId;
  const pageTitle = A && B ? `${A.name} vs ${B.name} — 同業對比` : "同業比較";
  const optionsForA = companies.filter(c => c.id !== bId);
  const optionsForB = companies.filter(c => c.id !== aId);

  return (
    <>
      <div className="page-scroll">
        <div className={"page peer-page research-layout" + (ctxOpen ? "" : " ctx-collapsed")}>
          <div className="rcol-main">
            <div className="page-head">
              <div className="page-eyebrow">同業比較 · peer</div>
              <h1 className="page-title">{pageTitle}</h1>
              <p className="page-desc">選擇兩間公司後送出查詢，或直接輸入「比較 A 與 B」由系統自動解析。</p>
            </div>

            {/* Company Slot Toolbar */}
            <div className="peer-toolbar" ref={slotRef}>
              <div className="ptb-vs">
                <CompanySlot
                  company={A} open={openSlot==="a"} search={slotSearch}
                  options={optionsForA} placeholder="選擇主體公司"
                  onToggle={() => toggleSlot("a")} onSearch={setSlotSearch}
                  onSelect={id => selectCompany("a", id)}
                />
                <span className="ptb-x font-mono">vs</span>
                <CompanySlot
                  company={B} open={openSlot==="b"} search={slotSearch}
                  options={optionsForB} placeholder="選擇比較對象"
                  onToggle={() => toggleSlot("b")} onSearch={setSlotSearch}
                  onSelect={id => selectCompany("b", id)}
                />
                {parseMsg.unknown.map((n,i) => (
                  <span key={i} className="parse-chip warn"><Icon name="alert" size={12}/>未識別：{n}</span>
                ))}
              </div>
              <div className="ptb-period">
                <select value={fiscalPeriod} onChange={e => setFiscalPeriod(e.target.value)}>
                  {availablePeriods.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            </div>

            {/* Comparison content */}
            {hasQueried && readyToCompare ? (
              <>
                <div className="mock-note">
                  <Icon name="alert" size={15}/>
                  <span><b>部分待接後端</b> — 「營收 YoY」已串接真實財務資料；毛利率、營業利益率等指標待 <code>POST /peer-compare</code> 上線後顯示，請勿引用。</span>
                </div>
                <div className="peer-l2"><PeerKpiGrid aName={A?.name??""} bName={B?.name??""} aTicker={aId} bTicker={bId}/></div>
                <TrendPanel aName={A?.name??""} bName={B?.name??""}/>
                <PeerSummaryPanel aName={A?.name??""} bName={B?.name??""}/>
                <div className="news-tabs peer-tabs">
                  {PEER_TABS.map(t => (
                    <button key={t.id} className={"news-tab"+(t.id===tab?" active":"")} onClick={() => switchTab(t.id)}>{t.label}</button>
                  ))}
                </div>
                <div className="peer-blocks">{renderBlock()}</div>
                <ComplianceBanner message="以上為事實對比，非投資建議。結構性差異已標註，合規檢查通過。"/>
              </>
            ) : (
              <div className="peer-empty">
                <Icon name="scale" size={28} style={{color:"rgb(var(--muted))",marginBottom:12}}/>
                <p>{!readyToCompare ? "請從上方選擇，或是輸入問題後開始分析" : "公司已選定，送出查詢後顯示比較結果"}</p>
              </div>
            )}

            {/* Actions */}
            <div className="actions">
              <button className="btn" disabled={!hasQueried} onClick={() => setShowReport(true)}>
                <Icon name="file" size={15}/>完整報告
              </button>
              <button className="btn ghost" disabled={running || !readyToCompare} onClick={() => runQuery()}>
                <Icon name="refresh" size={15}/>重新分析
              </button>
            </div>
          </div>

          {/* Sidebar */}
          <aside className="rcol-ctx">
            <button className="ctx-toggle-btn" onClick={()=>setCtxOpen(o=>!o)}>
              <Icon name={ctxOpen ? "chevR" : "panelLeft"} size={14}/>
              <span className="ctx-toggle-label">{ctxOpen ? "收起側欄" : "展開側欄"}</span>
            </button>
            <div className="panel ctx-panel">
              <div className="panel-head">
                <span className="panel-title"><Icon name="brain" size={15} style={{color:"rgb(var(--primary))",verticalAlign:"-3px",marginRight:6}}/>模型思考追蹤</span>
                <span className="panel-meta">ReAct</span>
              </div>
              {phase === "idle" ? (
                <div className="chart-empty" style={{padding:"20px 16px"}}>
                  <span>執行比較後顯示模型思考路徑</span>
                </div>
              ) : (
                <>
                  <div className="ctx-progress">
                    <div className="ctx-prog-track"><div className="ctx-prog-fill" style={{width:progress+"%"}}/></div>
                    <span className="font-mono">{running ? (curPhase ?? "") : "done"} · {progress}%</span>
                  </div>
                  {running && (
                    <div className="thinking-pulse">
                      <div className="thinking-dots"><span/><span/><span/></div>
                      <span>{thinkingLong ? "模型絞盡腦汁中，快好了" : "正在思考中"}</span>
                    </div>
                  )}
                  <ReActTrace steps={MOCK_REACT} activeIndex={running ? stepN-1 : undefined} visibleCount={running ? stepN : undefined}/>
                </>
              )}
            </div>
            <div className="panel ctx-panel">
              <div className="panel-head">
                <span className="panel-title"><Icon name="alert" size={14} style={{color:"rgb(var(--danger))",verticalAlign:"-2px",marginRight:6}}/>監控系統警示</span>
              </div>
              <div className="alert-list">
                {running
                  ? <div className="thinking-pulse" style={{padding:"14px 16px"}}>
                      <div className="thinking-dots"><span/><span/><span/></div>
                      <span>正在抓取資料中</span>
                    </div>
                  : peerAlerts.length > 0
                    ? peerAlerts.map((a,i) => (
                        <AlertItem key={a.id} alert={a} selected={selectedAlertIdx===i} read={rs.isRead(a.id)}
                          onClick={() => { setSelectedAlertIdx(selectedAlertIdx===i?null:i); rs.markRead(a.id); }}
                          onDoubleClick={() => { setModalAlert(a); rs.markRead(a.id); }}/>
                      ))
                    : <div className="chart-empty" style={{padding:"20px 16px"}}>
                        <Icon name="shield" size={18} style={{color:"rgb(var(--muted))",marginBottom:6}}/>
                        <span>{hasQueried ? "本次比較未發現異常訊號" : "執行比較後顯示相關警示"}</span>
                      </div>
                }
              </div>
            </div>
            <div className="panel ctx-panel">
              <div className="panel-head">
                <span className="panel-title"><Icon name="quote" size={14} style={{color:"rgb(var(--primary))",verticalAlign:"-2px",marginRight:6}}/>引用追蹤器</span>
                <span className="panel-meta">待接後端</span>
              </div>
              {running
                ? <div className="thinking-pulse" style={{padding:"14px 16px"}}>
                    <div className="thinking-dots"><span/><span/><span/></div>
                    <span>正在抓取資料中</span>
                  </div>
                : <div className="chart-empty" style={{padding:"20px 16px"}}>
                    <Icon name="quote" size={18} style={{color:"rgb(var(--muted))",marginBottom:6}}/>
                    <span>{hasQueried ? "引用來源待 POST /peer-compare 上線後顯示" : "執行比較後顯示引用來源"}</span>
                  </div>
              }
            </div>
          </aside>
        </div>
      </div>

      {/* Dock */}
      <div className="dock">
        <div className="dock-inner">
          <div className={`dock-chips${chipsFading ? " chips-fading" : ""}`}>
            {chips.map((p,i) => <button key={i} className="chip" onClick={() => { setQuery(p); runQuery(p); }}>{p}</button>)}
          </div>
          <div className="dock-row">
            <Icon name="spark" size={18} style={{color:"rgb(var(--primary))",flexShrink:0}}/>
            <input className="dock-input" value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if(e.key==="Enter"&&(e.ctrlKey||e.metaKey||!e.shiftKey)) runQuery(); }}
              placeholder="輸入欲比較的公司，例如：比較台積電與聯發科財務... (Enter 送出)"/>
            <button className={"dock-tool" + (isListening ? " active" : "")} title={isListening ? "聆聽中…" : "語音輸入"} onClick={startVoice} disabled={running}><Icon name="mic" size={19}/></button>
            <button className={"btn primary dock-send" + (running ? " sending" : "")} onClick={() => runQuery()} disabled={running}>
              <Icon name={running ? "refresh" : "send"} size={18}/>
            </button>
          </div>
          <div className="dock-hint">選擇公司插槽或輸入自然語言 · 自動解析公司／季別／維度 · 非投資建議</div>
        </div>
      </div>

      {/* Alert Modal */}
      {modalAlert && (
        <div className="alert-modal-overlay" onClick={() => setModalAlert(null)}>
          <div className="alert-modal" onClick={e => e.stopPropagation()}>
            <div className="alert-modal-head">
              <h2>{modalAlert.title}</h2>
              <button className="alert-modal-close" onClick={() => setModalAlert(null)}><Icon name="x" size={18}/></button>
            </div>
            <div className="alert-modal-body">
              <div className="alert-modal-tag">
                <span className={"tag "+modalAlert.level}><span className="tdot"/>
                  {modalAlert.level==="high"?"高":modalAlert.level==="mid"?"中":"低"}
                </span>
              </div>
              <p>{modalAlert.summary}</p>
              <div className="alert-modal-meta font-mono">{modalAlert.source} · {modalAlert.time}</div>
            </div>
          </div>
        </div>
      )}

      {/* Report Modal */}
      {showReport && A && B && (
        <ReportModal
          query={`${A.name} vs ${B.name} 同業比較`}
          kpis={buildPeerReportKpis(A.name, B.name)}
          summary={buildPeerReportSummary(A.name, B.name)}
          react={MOCK_REACT}
          citations={[]}
          onClose={() => setShowReport(false)}
        />
      )}

      <DocViewer doc={openDoc} onClose={() => setOpenDoc(null)}/>
    </>
  );
}
