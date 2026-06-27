"use client";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import type { KpiVM, SummaryItemVM, TraceStepVM, CitationTrackerVM } from "@/types/viewmodel";
import { fmtFinNum } from "@/lib/formatters";

interface Props {
  query: string;
  kpis: KpiVM[];
  summary: SummaryItemVM[];
  react: TraceStepVM[];
  citations: CitationTrackerVM[];
  onClose: () => void;
}

export function ReportModal({ query, kpis, summary, react, citations, onClose }: Props) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    document.body.classList.add("report-open");
    return () => document.body.classList.remove("report-open");
  }, []);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [onClose]);

  const handleExportPDF = async () => {
    const el = bodyRef.current;
    if (!el || exporting) return;
    setExporting(true);

    const controls = el.querySelectorAll<HTMLElement>(".report-close-btn");
    controls.forEach(c => { c.style.visibility = "hidden"; });
    const footer = el.querySelector<HTMLElement>(".report-footer");
    if (footer) footer.style.display = "none";
    // PDF 不含引用來源與模型思考路徑
    const pdfHide = el.querySelectorAll<HTMLElement>(".report-pdf-hide");
    pdfHide.forEach(e => { e.style.display = "none"; });
    // 強制亮色模式捕捉，避免深色模式文字在白底 PDF 上不可讀
    const htmlEl = document.documentElement;
    const prevTheme = htmlEl.getAttribute("data-theme");

    const prevMaxWidth = el.style.maxWidth;
    const prevWidth    = el.style.width;

    try {
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);

      const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
      const pageW = pdf.internal.pageSize.getWidth();   // 210 mm
      const pageH = pdf.internal.pageSize.getHeight();  // 297 mm
      const margin   = 14;
      const contentW = pageW - margin * 2;  // 182 mm
      const contentH = pageH - margin * 2;  // 269 mm

      // Shrink modal to A4 content width at 96 dpi (≈688 px) before capture so
      // CSS px sizes map to correct pt sizes in the PDF (≈11 pt body text).
      const renderPx = Math.round(contentW / 25.4 * 96);
      el.style.maxWidth = renderPx + "px";
      el.style.width    = renderPx + "px";
      htmlEl.setAttribute("data-theme", "light");
      await new Promise<void>(resolve => setTimeout(resolve, 0));

      const canvas = await html2canvas(el, {
        scale: 2,
        useCORS: true,
        backgroundColor: "#ffffff",
        logging: false,
      });

      // px per mm of content width
      const pxPerMm       = canvas.width / contentW;
      const pageContentPx = Math.round(contentH * pxPerMm);
      const totalPages    = Math.ceil(canvas.height / pageContentPx);

      for (let page = 0; page < totalPages; page++) {
        if (page > 0) pdf.addPage();

        const srcY = page * pageContentPx;
        const srcH = Math.min(pageContentPx, canvas.height - srcY);

        // slice exactly this page's pixels — top/bottom margins clean by construction
        const slice = document.createElement("canvas");
        slice.width  = canvas.width;
        slice.height = srcH;
        const sctx = slice.getContext("2d")!;
        sctx.fillStyle = "#ffffff";
        sctx.fillRect(0, 0, slice.width, slice.height);
        sctx.drawImage(canvas, 0, srcY, canvas.width, srcH, 0, 0, canvas.width, srcH);

        pdf.addImage(slice.toDataURL("image/png"), "PNG", margin, margin, contentW, srcH / pxPerMm);
      }

      const filename = `${query.slice(0, 40).replace(/[/\\:*?"<>|]/g, "_")}_研究報告.pdf`;
      pdf.save(filename);
    } finally {
      el.style.maxWidth = prevMaxWidth;
      el.style.width    = prevWidth;
      if (footer) footer.style.display = "";
      controls.forEach(c => { c.style.visibility = ""; });
      pdfHide.forEach(e => { e.style.display = ""; });
      if (prevTheme) htmlEl.setAttribute("data-theme", prevTheme);
      else htmlEl.removeAttribute("data-theme");
      setExporting(false);
    }
  };

  const date = new Date().toLocaleDateString("zh-TW", { year: "numeric", month: "long", day: "numeric" });

  return (
    <div className="report-overlay show" onClick={onClose}>
      <div className="report-body" ref={bodyRef} onClick={e => e.stopPropagation()}>

        <div className="report-head">
          <div className="report-head-info">
            <div className="report-eyebrow font-mono">研究報告 · Polaris Desk · {date}</div>
            <h1 className="report-title">{query}</h1>
          </div>
          <div className="report-head-actions">
            <button className="btn ghost report-close-btn" onClick={onClose}>
              <Icon name="x" size={16}/>
            </button>
          </div>
        </div>

        <div className="report-content">
          <section className="report-section" style={{ marginTop: 0, marginBottom: 20 }}>
            <div style={{
              display: "flex", gap: 10, alignItems: "flex-start",
              padding: "12px 16px", borderRadius: 6,
              background: "rgb(192 64 54 / 0.06)",
              border: "1px solid rgb(192 64 54 / 0.25)",
            }}>
              <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>⚠</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 14, color: "rgb(192 64 54)", marginBottom: 5 }}>
                  合規聲明
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.7, color: "rgb(23 25 31 / 0.75)" }}>
                  本報告為事實性資料摘要，每項結論均附有可溯源之原始文件引用（法說會逐字稿、財務報表或新聞公告）。
                  本報告<strong>不構成任何投資建議、買賣建議或對特定有價證券之推薦</strong>。
                  投資決策應自行判斷並承擔相關風險。
                </div>
                <div style={{ fontSize: 12, color: "rgb(23 25 31 / 0.45)", marginTop: 5 }}>
                  報告產出時間：{date}｜資料以產出當下為準，後續更新恕不另行通知。
                </div>
              </div>
            </div>
          </section>

          {kpis.length > 0 && (
            <section className="report-section">
              <h2 className="report-sec-title">關鍵指標</h2>
              <div className="report-kpi-grid">
                {kpis.map((k, i) => (
                  <div key={i} className="report-kpi">
                    <div className="report-kpi-label">{k.label}</div>
                    <div className="report-kpi-value font-mono">
                      {fmtFinNum(k.value)}<span className="report-kpi-unit">{k.unit}</span>
                    </div>
                    <div className={"report-kpi-delta " + k.trend}>{k.delta}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {summary.length > 0 && (
            <section className="report-section">
              <h2 className="report-sec-title">營運重點摘要</h2>
              <ul className="report-summary">
                {summary.map((s, i) => (
                  <li key={i}>{s.text}</li>
                ))}
              </ul>
            </section>
          )}

          {citations.length > 0 && (
            <section className="report-section report-pdf-hide">
              <h2 className="report-sec-title">引用來源</h2>
              <div className="report-cite-list">
                {citations.map((c, i) => (
                  <div key={i} className="report-cite-row">
                    <span className="report-cite-ix font-mono">[{c.ix}]</span>
                    <span className="report-cite-label">{c.label}</span>
                    <span className="report-cite-detail">{c.detail}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {react.length > 0 && (
            <section className="report-section report-pdf-hide">
              <h2 className="report-sec-title">模型思考路徑</h2>
              <div className="report-react">
                {react.map((s, i) => (
                  <div key={i} className={"report-step rs-" + s.type.toLowerCase()}>
                    <span className="report-step-type font-mono">{s.type}</span>
                    <span className="report-step-text">{s.text}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="report-footer">
          <span>本報告由 Polaris Desk AI 生成，每筆結論皆有原始文件引用。</span>
          <div className="report-footer-actions">
            <span className="report-nfr-tag">⚠ 本內容不構成投資建議</span>
            <button className="btn report-export-btn" onClick={handleExportPDF} disabled={exporting}>
              <Icon name="download" size={15}/>
              {exporting ? "生成中…" : "匯出 PDF"}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
