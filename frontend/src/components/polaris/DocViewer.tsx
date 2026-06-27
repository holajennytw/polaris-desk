"use client";
import { useEffect } from "react";
import { Icon } from "@/components/ui/Icon";

export interface DocContent {
  key: string;
  title: string;
  kind: string;
  source_id: string;
  page: string;
  period?: string;
  trust: "high" | "mid" | "low";
  highlight: string;
  hlTokens?: string[];
  body: string[];
}

interface DocViewerProps {
  doc: DocContent | null;
  onClose: () => void;
}

export function DocViewer({ doc, onClose }: DocViewerProps) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  return (
    <div className={"dv-overlay" + (doc ? " show" : "")} onClick={onClose}>
      <div className="dv-sheet" onClick={(e) => e.stopPropagation()}>
        {doc && (
          <>
            <div className="dv-head">
              <div className="dv-kind">
                <Icon name="file" size={14} />
                {doc.kind}
              </div>
              <button className="icon-btn" onClick={onClose} aria-label="關閉文件">
                <Icon name="x" size={18} />
              </button>
            </div>
            <div className="dv-title-row">
              <div className="dv-title">{doc.title}</div>
              <div className="dv-sub">
                <span className="tag ok">
                  <span className="tdot" />
                  可信度 {doc.trust === "high" ? "高" : "中"}
                </span>
                <span className="font-mono dv-page">{doc.page}</span>
              </div>
            </div>
            <div className="dv-body">
              <div className="pdf-mock">
                <div className="pdf-bar">
                  <span>{doc.kind}</span>
                  <span className="font-mono">{doc.period ?? doc.page}</span>
                </div>
                {doc.body.map((line, i) => {
                  const hit = (doc.hlTokens || []).some((t) => line.includes(t));
                  return (
                    <div key={i} className={"pdf-line" + (hit ? " hl" : "")}>
                      {line}
                    </div>
                  );
                })}
              </div>
              <div className="dv-chunk">
                <div className="dv-chunk-label">
                  <Icon name="quote" size={13} />
                  引用片段 · {doc.kind}{doc.period ? ` · ${doc.period}` : ""}
                </div>
                <p>{doc.highlight}</p>
              </div>
              <div className="compliance" style={{ marginTop: 14 }}>
                <Icon name="shield" />
                <span>
                  <b>來源已驗證</b>{" "}
                  <span className="ctxt">
                    — 此 chunk 來自原始文件，未經改寫，可逐字溯源至 {doc.page}。
                  </span>
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
