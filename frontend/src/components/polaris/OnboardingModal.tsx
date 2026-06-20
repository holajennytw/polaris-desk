"use client";
import { useState, useEffect } from "react";
import { useSession, signIn } from "next-auth/react";
import { Icon } from "@/components/ui/Icon";

const STORAGE_KEY = "polaris-onboarded";

const STEPS = [
  {
    icon: "star" as const,
    title: "歡迎使用 Polaris Desk",
    body: "這是可溯源 AI 研究助理。Polaris Desk 結合推理、逐字引用追蹤與合規檢查，讓您在數秒內得到有來源、可稽核的研究結論。",
    tip: null,
    cta: null,
  },
  {
    icon: "brain" as const,
    title: "研究助理",
    body: "在查詢列輸入股票問題，系統會透過推理、檢索、計算與交叉驗證，輸出重點摘要並掛載原文引用來源。",
    tip: "試試：台積電 2026Q1 法說會重點",
    cta: "/research",
  },
  {
    icon: "scale" as const,
    title: "同業比較",
    body: "輸入兩家公司，系統會解析財務指標、法說等相關重點，並逐欄交叉驗證數字，以 GICS 拆解解釋毛利率差異來源。",
    tip: "試試：台積電 vs 聯發科 毛利率比較",
    cta: "/peer",
  },
  {
    icon: "quote" as const,
    title: "引用追蹤 & 合規說明",
    body: "每個數字與結論皆引用 chip，點擊即可開啟原始財報並逐字高亮。所有 AI 輸出均為事實摘要，不構成任何投資建議（NFR-031）。",
    tip: "登入後可儲存研究紀錄，隨時回顧歷史分析",
    cta: null,
  },
];

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" style={{ flexShrink: 0 }}>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.76h3.56c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.56-2.76c-.98.66-2.23 1.06-3.72 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.11a6.6 6.6 0 0 1 0-4.22V7.05H2.18a11 11 0 0 0 0 9.9z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.05l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/>
    </svg>
  );
}

export function OnboardingModal() {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!localStorage.getItem(STORAGE_KEY)) {
      setOpen(true);
    }
  }, []);

  const dismiss = () => {
    setClosing(true);
    setTimeout(() => {
      localStorage.setItem(STORAGE_KEY, "1");
      // Fix Bug 5: 通知同一 tab 的 ResearchTour（localStorage 寫入不觸發 storage 事件）
      window.dispatchEvent(new CustomEvent("polaris:onboarded"));
      setOpen(false);
      setClosing(false);
    }, 180);
  };

  if (!open) return null;

  const cur = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const isFirst = step === 0;

  return (
    <div
      className="alert-modal-overlay"
      style={{ zIndex: 300, opacity: closing ? 0 : 1, transition: "opacity 0.18s" }}
      onClick={dismiss}
    >
      <div
        className="alert-modal"
        onClick={e => e.stopPropagation()}
        style={{
          maxWidth: 460,
          width: "90vw",
          transform: closing ? "translateY(12px)" : "translateY(0)",
          opacity: closing ? 0 : 1,
          transition: "transform 0.18s, opacity 0.18s",
        }}
      >
        {/* Header */}
        <div className="alert-modal-head">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: "rgb(var(--primary) / 0.12)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "rgb(var(--primary))", flexShrink: 0,
            }}>
              <Icon name={cur.icon} size={18} />
            </div>
            <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0, color: "rgb(var(--foreground))" }}>
              {cur.title}
            </h2>
          </div>
          <button className="alert-modal-close" onClick={dismiss} aria-label="關閉">
            <Icon name="x" size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="alert-modal-body" style={{ padding: "16px 20px 8px" }}>
          <p style={{ lineHeight: 1.75, color: "rgb(var(--foreground))", margin: 0, fontSize: 14 }}>
            {cur.body}
          </p>

          {cur.tip && (
            <div style={{
              marginTop: 12, padding: "8px 12px", borderRadius: 8,
              background: "rgb(var(--primary) / 0.07)",
              color: "rgb(var(--primary))",
              fontSize: 13, fontFamily: "var(--font-mono)",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <Icon name="spark" size={13} style={{ flexShrink: 0 }} />
              {cur.tip}
            </div>
          )}

          {/* Last step: Google login if not signed in */}
          {isLast && !session && (
            <button
              className="sso-btn"
              onClick={() => signIn("google")}
              style={{ marginTop: 14, width: "100%", justifyContent: "center" }}
            >
              <GoogleMark />
              <span>使用 Google 帳號登入以儲存研究紀錄</span>
            </button>
          )}

          {/* Last step: already signed in */}
          {isLast && session && (
            <div style={{
              marginTop: 12, padding: "8px 12px", borderRadius: 8,
              background: "rgb(var(--success) / 0.08)",
              color: "rgb(var(--success))",
              fontSize: 13,
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <Icon name="check" size={13} style={{ flexShrink: 0 }} />
              已登入為 {session.user?.name ?? session.user?.email}，研究紀錄會自動儲存。
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 20px 16px",
          borderTop: "1px solid rgb(var(--border))",
        }}>
          {/* Step dots */}
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {STEPS.map((_, i) => (
              <button
                key={i}
                aria-label={`步驟 ${i + 1}`}
                onClick={() => setStep(i)}
                style={{
                  width: i === step ? 20 : 7,
                  height: 7,
                  borderRadius: 4,
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                  background: i === step
                    ? "rgb(var(--primary))"
                    : i < step
                      ? "rgb(var(--primary) / 0.4)"
                      : "rgb(var(--border))",
                  transition: "all 0.22s",
                }}
              />
            ))}
          </div>

          {/* Navigation buttons */}
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {!isFirst && (
              <button
                className="btn ghost"
                style={{ fontSize: 13 }}
                onClick={() => setStep(s => s - 1)}
              >
                <Icon name="chevR" size={13} style={{ transform: "rotate(180deg)" }} />
                上一步
              </button>
            )}
            <button
              className="btn ghost"
              style={{ fontSize: 13, color: "rgb(var(--muted))" }}
              onClick={dismiss}
            >
              跳過
            </button>
            {isLast ? (
              <button className="btn primary" style={{ fontSize: 13 }} onClick={dismiss}>
                開始使用
                <Icon name="arrowRight" size={14} />
              </button>
            ) : (
              <button className="btn primary" style={{ fontSize: 13 }} onClick={() => setStep(s => s + 1)}>
                下一步
                <Icon name="arrowRight" size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
