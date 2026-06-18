"use client";
import { useState } from "react";
import { Icon } from "@/components/ui/Icon";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { HistoryEntry } from "@/lib/historyStore";

const FILTER_TABS = ["all", "research", "peer"];
const TAB_LABELS: Record<string, string> = { all: "全部", research: "研究助理", peer: "同業比較" };

const GROUP_LABELS = { today: "今日", thisWeek: "本週", earlier: "更早" } as const;
type Group = keyof typeof GROUP_LABELS;
const GROUP_ORDER: Group[] = ["today", "thisWeek", "earlier"];

function getGroup(id: string): Group {
  const ts = parseInt(id.replace("hist-", ""), 10);
  if (isNaN(ts)) return "earlier";
  const now = new Date();
  const d = new Date(ts);
  if (d.toDateString() === now.toDateString()) return "today";
  if (now.getTime() - ts < 7 * 86400000) return "thisWeek";
  return "earlier";
}

function groupItems(items: HistoryEntry[]) {
  const buckets: Partial<Record<Group, HistoryEntry[]>> = {};
  for (const item of items) {
    const g = getGroup(item.id);
    (buckets[g] ??= []).push(item);
  }
  return GROUP_ORDER
    .filter(g => buckets[g]?.length)
    .map(g => ({ key: g, label: GROUP_LABELS[g], items: buckets[g]! }));
}

export default function HistoryPage() {
  const { data, isLoading } = useSWR("history", () => api.history());
  const [filter, setFilter] = useState("all");

  const filtered = (data ?? []).filter(item => filter === "all" || item.page === filter);
  const groups = groupItems(filtered);

  return (
    <div className="page-scroll">
      <div className="page narrow">
        <div className="page-head">
          <div className="page-eyebrow">對話紀錄 · /history</div>
          <h1 className="page-title">對話紀錄</h1>
          <p className="page-desc">所有研究查詢與同業比較的歷史紀錄。</p>
        </div>
        <div className="news-tabs">
          {FILTER_TABS.map(t => (
            <button key={t} className={"news-tab" + (t === filter ? " active" : "")} onClick={() => setFilter(t)}>
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>
        {isLoading ? (
          <div style={{ padding: 24, color: "rgb(var(--muted))" }}>載入中...</div>
        ) : groups.length === 0 ? (
          <div className="panel" style={{ marginTop: 16 }}>
            <div style={{ padding: "48px 16px", textAlign: "center", color: "rgb(var(--muted))" }}>
              <Icon name="clock" size={32} style={{ marginBottom: 10, opacity: 0.3 }}/>
              <div>目前無紀錄</div>
            </div>
          </div>
        ) : (
          <div className="panel" style={{ marginTop: 16 }}>
            {groups.map((group, gi) => (
              <div key={group.key}>
                <div style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "rgb(var(--muted))",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  padding: gi === 0 ? "14px 16px 6px" : "24px 16px 6px",
                  fontFamily: "var(--mono)",
                }}>
                  {group.label}
                </div>
                {group.items.map((item, i) => (
                  <Link
                    key={item.id}
                    href={"/" + item.page + "?q=" + encodeURIComponent(item.query)}
                    className="history-item"
                    style={{ animationDelay: `${i * 45}ms` }}
                  >
                    <div className="ni-icon">
                      <Icon name={item.page === "peer" ? "scale" : "brain"} size={17} />
                    </div>
                    <div className="history-body">
                      <div className="history-query">
                        {item.query || (
                          <span style={{ color: "rgb(var(--muted))" }}>
                            {item.page === "peer" ? "同業比較查詢" : "研究助理查詢"}
                          </span>
                        )}
                      </div>
                      <div className="history-meta font-mono">
                        {item.page === "peer" ? "同業比較" : "研究助理"} · {item.time}
                      </div>
                    </div>
                    <div className="history-tags">
                      {item.tags.map((t, ti) => <span key={ti} className="tag muted" style={{ fontSize: 12 }}>{t}</span>)}
                    </div>
                    <Icon name="chevR" size={15} style={{ color: "rgb(var(--muted))", flexShrink: 0 }}/>
                  </Link>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
