"use client";
import { useState } from "react";
import { Icon } from "@/components/ui/Icon";
import useSWR from "swr";
import { api } from "@/lib/api";

const SOURCES = ["all","財報","法說會","逐字稿","績效報告"];

export default function LibraryPage() {
  const { data, isLoading } = useSWR("library", ()=>api.library());
  const [typeTab, setTypeTab] = useState("all");
  const [source, setSource] = useState("all");

  const types = data?.types ?? [];
  const allDocs = data?.docs ?? [];
  const docs = allDocs.filter(d=>{
    const typeOk = typeTab==="all" || d.kind===types.find(t=>t.id===typeTab)?.label;
    return typeOk;
  });

  return (
    <div className="page-scroll">
      <div className="page">
        <div className="page-head">
          <div className="page-eyebrow">資料庫 · /library</div>
          <h1 className="page-title">研究資料庫</h1>
          <p className="page-desc">管理已建索引的財報、法說會逐字稿與績效報告。</p>
        </div>
        {data?.stats && (
          <div className="kpi-grid" style={{gridTemplateColumns:"repeat(auto-fit,minmax(140px,1fr))",marginBottom:24}}>
            {data.stats.map((s,i)=>(
              <div key={i} className="card" style={{padding:16}}>
                <div style={{fontSize:13,color:"rgb(var(--muted))",marginBottom:4}}>{s.label}</div>
                <div className="font-display" style={{fontSize:24,fontWeight:700}}>{s.value}</div>
              </div>
            ))}
          </div>
        )}
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:16,flexWrap:"wrap"}}>
          <div className="news-tabs" style={{margin:0}}>
            {types.map(t=>(
              <button key={t.id} className={"news-tab"+(t.id===typeTab?" active":"")} onClick={()=>setTypeTab(t.id)}>
                {t.label}<span className="font-mono" style={{fontSize:12,marginLeft:4,color:"rgb(var(--muted))"}}>{t.count}</span>
              </button>
            ))}
          </div>
          <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:8}}>
            <Icon name="database" size={14} style={{color:"rgb(var(--muted))"}}/>
            <select className="font-mono" style={{fontSize:13,border:"1px solid rgb(var(--border))",borderRadius:"var(--radius-sm)",padding:"6px 10px",background:"rgb(var(--card))",color:"rgb(var(--foreground))"}} value={source} onChange={e=>setSource(e.target.value)}>
              {SOURCES.map(s=><option key={s} value={s}>{s==="all"?"全部來源":s}</option>)}
            </select>
          </div>
        </div>
        {isLoading ? (
          <div style={{padding:24,color:"rgb(var(--muted))"}}>載入中...</div>
        ) : (
          <div className="panel">
            <table className="ptable" style={{width:"100%"}}>
              <thead>
                <tr>
                  <th>文件</th><th>公司</th><th>期間</th><th>類型</th><th>頁數</th><th>狀態</th><th>更新</th>
                </tr>
              </thead>
              <tbody>
                {docs.map(doc=>(
                  <tr key={doc.id}>
                    <td><div style={{fontWeight:600,marginBottom:2}}>{doc.title}</div><div className="font-mono" style={{fontSize:12,color:"rgb(var(--muted))"}}>{doc.size}</div></td>
                    <td>{doc.company}</td>
                    <td className="font-mono">{doc.period}</td>
                    <td><span className="tag muted">{doc.kind}</span></td>
                    <td className="font-mono">{doc.pages}</td>
                    <td>{doc.ingested ? <span className="tag ok"><span className="tdot"/>已建索引</span> : <span className="tag warn"><span className="tdot"/>待處理</span>}</td>
                    <td className="font-mono" style={{fontSize:13,color:"rgb(var(--muted))"}}>{doc.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}