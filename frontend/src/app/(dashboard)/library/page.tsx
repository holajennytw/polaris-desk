"use client";
import { useState } from "react";
import { Icon } from "@/components/ui/Icon";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useCompanies } from "@/hooks/useCompanies";

const TYPE_TABS = ["all", "major_news", "transcript", "earnings_call"] as const;
type TypeTab = typeof TYPE_TABS[number];

const TYPE_LABELS: Record<string, string> = {
  all: "全部",
  major_news: "重大訊息",
  transcript: "法說會逐字稿",
  earnings_call: "法說會",
};

export default function LibraryPage() {
  const { data, isLoading } = useSWR("library", () => api.library());
  const companies = useCompanies();
  const [typeTab, setTypeTab] = useState<TypeTab>("all");
  const [tickerTab, setTickerTab] = useState("all");

  const allDocs = data?.docs ?? [];

  const docTickers = new Set(allDocs.map(d => d.ticker));
  const tickerTabs = companies.filter(c => docTickers.has(c.id));

  const docs = allDocs.filter(d => {
    const typeOk = typeTab === "all" || d.doc_type === typeTab;
    const tickerOk = tickerTab === "all" || d.ticker === tickerTab;
    return typeOk && tickerOk;
  });

  return (
    <div className="page-scroll">
      <div className="page narrow">
        <div className="page-head">
          <div className="page-eyebrow">資料庫 · library</div>
          <h1 className="page-title">資料庫</h1>
          <p className="page-desc">檢視已有的的財報、法說會與績效等相關報告。</p>
        </div>

        {data?.stats && (
          <div className="kpi-grid" style={{gridTemplateColumns:"repeat(auto-fit,minmax(140px,1fr))",marginBottom:24}}>
            {data.stats.map((s, i) => (
              <div key={i} className="card" style={{padding:16}}>
                <div style={{fontSize:13,color:"rgb(var(--muted))",marginBottom:4}}>{s.label}</div>
                <div className="font-display" style={{fontSize:24,fontWeight:700}}>{s.value}</div>
              </div>
            ))}
          </div>
        )}

        <div className="news-tabs">
          {TYPE_TABS.map(t => (
            <button
              key={t}
              className={"news-tab" + (t === typeTab ? " active" : "")}
              onClick={() => setTypeTab(t)}
            >
              {TYPE_LABELS[t]}
            </button>
          ))}
        </div>

        {tickerTabs.length > 0 && (
          <div className="news-tabs">
            <button className={"news-tab" + (tickerTab === "all" ? " active" : "")} onClick={() => setTickerTab("all")}>全部公司</button>
            {tickerTabs.map(c => (
              <button key={c.id} className={"news-tab" + (c.id === tickerTab ? " active" : "")} onClick={() => setTickerTab(c.id)}>
                {c.name}<span className="font-mono" style={{fontSize:16,marginLeft:5,opacity:0.6}}>{c.id}</span>
              </button>
            ))}
          </div>
        )}

        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">
              <Icon name="database" size={15} style={{color:"rgb(var(--primary))",verticalAlign:"-2px",marginRight:6}}/>
              文件列表
            </span>
            {!isLoading && <span className="panel-meta">{docs.length} 份</span>}
          </div>

          {isLoading ? (
            <div style={{padding:"48px 16px",textAlign:"center",color:"rgb(var(--muted))"}}>
              <Icon name="database" size={28} style={{marginBottom:10,opacity:0.25}}/>
              <div>載入中...</div>
            </div>
          ) : docs.length === 0 ? (
            <div style={{padding:"48px 16px",textAlign:"center",color:"rgb(var(--muted))"}}>
              <Icon name="file" size={32} style={{marginBottom:10,opacity:0.25}}/>
              <div style={{fontWeight:500,marginBottom:4}}>無符合條件的文件</div>
              <div style={{fontSize:13}}>請調整分類篩選</div>
            </div>
          ) : (
            <div className="ptable-wrap">
              <table className="ptable" style={{width:"100%"}}>
                <thead>
                  <tr>
                    <th>文件</th>
                    <th>代號</th>
                    <th>公司</th>
                    <th>期間</th>
                    <th>類型</th>
                    <th>頁數</th>
                    <th>狀態</th>
                    <th>發布日</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map(doc => (
                    <tr key={doc.id}>
                      <td>
                        <div style={{fontWeight:600,marginBottom:2}}>{doc.source_file}</div>
                        {doc.fetched_at && (
                          <div className="font-mono" style={{fontSize:16,color:"rgb(var(--muted))"}}>入庫 {doc.fetched_at}</div>
                        )}
                      </td>
                      <td className="font-mono">{doc.ticker}</td>
                      <td>{doc.company_name}</td>
                      <td className="font-mono">{doc.fiscal_period}</td>
                      <td><span className="tag muted">{TYPE_LABELS[doc.doc_type] ?? doc.doc_type}</span></td>
                      <td className="font-mono">{doc.page_count}</td>
                      <td>
                        {doc.ingested
                          ? <span className="tag ok"><span className="tdot"/>已建索引</span>
                          : <span className="tag muted"><span className="tdot"/>待處理</span>
                        }
                      </td>
                      <td className="font-mono" style={{fontSize:16,color:"rgb(var(--muted))"}}>{doc.published_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
