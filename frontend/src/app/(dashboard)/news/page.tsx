"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

export default function NewsPage() {
  const { data, isLoading } = useSWR("news", () => api.news());
  const [tab, setTab] = useState("all");

  const tabs = data?.tabs ?? [{ id: "all", label: "全部", count: 0 }];
  const items = (data?.items ?? []).filter(
    (item) =>
      tab === "all" ||
      item.tags.some((t) => t === tabs.find((tb) => tb.id === tab)?.label)
  );

  return (
    <div className="page-scroll">
      <div className="page" style={{ maxWidth: 800 }}>
        <div className="page-head">
          <div className="page-eyebrow">新聞 · /news</div>
          <h1 className="page-title" style={{ fontSize: 24 }}>市場新聞</h1>
          {data?.updated && (
            <div className="font-mono" style={{ fontSize: 13, color: "rgb(var(--muted))" }}>
              更新：{data.updated}
            </div>
          )}
        </div>
        <div className="news-tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={"news-tab" + (t.id === tab ? " active" : "")}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.count > 0 && (
                <span className="font-mono" style={{ fontSize: 12, marginLeft: 4, color: "rgb(var(--muted))" }}>
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>
        {isLoading ? (
          <div style={{ padding: 24, color: "rgb(var(--muted))" }}>載入中...</div>
        ) : items.length === 0 ? (
          <div style={{ padding: 24, color: "rgb(var(--muted))" }}>暫無新聞資料</div>
        ) : (
          <div className="news-feed">
            {items.map((item) => (
              <div key={item.id} className="news-item">
                <div className="ni-source font-mono">{item.cite} · {item.time}</div>
                {item.url ? (
                  <a
                    className="ni-title"
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "inherit", textDecoration: "none", display: "block" }}
                  >
                    {item.title}
                  </a>
                ) : (
                  <div className="ni-title">{item.title}</div>
                )}
                {item.tags.length > 0 && (
                  <div className="ni-tags">
                    {item.tags.map((t, i) => (
                      <span key={i} className="tag muted">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
