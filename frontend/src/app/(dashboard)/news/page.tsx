"use client";
import { useState } from "react";
import useSWR from "swr";
import { Icon } from "@/components/ui/Icon";
import { api } from "@/lib/api";
import { useCompanies } from "@/hooks/useCompanies";

function fmtDate(s: string): string {
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return s;
  return `${parseInt(m[2])}月${parseInt(m[3])}日`;
}

export default function NewsPage() {
  const { data, isLoading } = useSWR("news", () => api.news());
  const companies = useCompanies();
  const [tab, setTab] = useState("all");

  const tickerToName = Object.fromEntries(companies.map(c => [c.id, c.name]));

  const tabs = data?.tabs ?? [{ id: "all", label: "全部", count: 0 }];
  const items = (data?.items ?? []).filter(
    (item) =>
      tab === "all" ||
      item.tags.some((t) => t === tabs.find((tb) => tb.id === tab)?.label)
  );

  return (
    <div className="page-scroll">
      <div className="page narrow">
        <div className="page-head">
          <div className="page-eyebrow">新聞 · /news</div>
          <h1 className="page-title">市場新聞</h1>
          {data?.updated && (
            <p className="page-desc">更新：{data.updated}</p>
          )}
        </div>

        <div className="news-tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={"news-tab" + (t.id === tab ? " active" : "")}
              onClick={() => setTab(t.id)}
            >
              {t.id === "all" ? "全部" : (tickerToName[t.id] ?? t.label)}
              {t.count > 0 && (
                <span className="font-mono" style={{ fontSize: 16, marginLeft: 5, opacity: 0.6 }}>
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="panel" style={{ marginTop: 16 }}>
          <div className="panel-head">
            <span className="panel-title">
              <Icon name="news" size={15} style={{ color: "rgb(var(--primary))", verticalAlign: "-2px", marginRight: 6 }} />
              新聞列表
            </span>
            {!isLoading && (
              <span className="panel-meta">{items.length} 則</span>
            )}
          </div>

          {isLoading ? (
            <div style={{ padding: "48px 16px", textAlign: "center", color: "rgb(var(--muted))" }}>
              <Icon name="news" size={28} style={{ marginBottom: 10, opacity: 0.25 }} />
              <div>載入中...</div>
            </div>
          ) : items.length === 0 ? (
            <div style={{ padding: "48px 16px", textAlign: "center", color: "rgb(var(--muted))" }}>
              <Icon name="news" size={32} style={{ marginBottom: 10, opacity: 0.25 }} />
              <div style={{ fontWeight: 500, marginBottom: 4 }}>暫無新聞資料</div>
              <div style={{ fontSize: 13 }}>目前所選分類無可顯示的新聞</div>
            </div>
          ) : (
            items.map((item, i) => {
              const sourceName = tickerToName[item.cite] ?? item.cite;
              const row = (
                <div
                  key={item.id}
                  className="news-row"
                  style={{ animationDelay: `${i * 45}ms` }}
                >
                  <div className="ni-icon">
                    <Icon name="news" size={17} />
                  </div>
                  <div className="ni-body">
                    <div className="ni-title">{item.title}</div>
                    <div className="ni-meta font-mono">
                      {sourceName}
                      {item.cite !== sourceName && (
                        <span style={{ opacity: 0.55, marginLeft: 4 }}>{item.cite}</span>
                      )}
                      {item.time && <> · {fmtDate(item.time)}</>}
                    </div>
                    {item.tags.length > 0 && (
                      <div className="sr-only" aria-label={`標籤：${item.tags.map(t => tickerToName[t] ?? t).join("、")}`} />
                    )}
                  </div>
                  <Icon name="chevR" size={15} style={{ color: "rgb(var(--muted))", flexShrink: 0 }} />
                </div>
              );

              return item.url ? (
                <a
                  key={item.id}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: "none", color: "inherit", display: "block" }}
                >
                  {row}
                </a>
              ) : row;
            })
          )}
        </div>
      </div>
    </div>
  );
}
