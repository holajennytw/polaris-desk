"use client";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";

const STORAGE_KEY  = "polaris-research-toured";
const ONBOARD_KEY  = "polaris-onboarded";
const LOADING_TIMEOUT_MS = 30_000;

interface Step {
  icon: "spark" | "brain" | "layers" | "quote" | "check" | "alert" | "panelLeft";
  title: string;
  body: string;
  selector: string | null;
  fallbackSelector: string | null;
  secondarySelector?: string | null;
  isAction?: boolean;
  isEnd?: boolean;
}

const STEPS: Step[] = [
  {
    icon: "spark",
    title: "快速開始",
    body: "點選預設問題可快速體驗研究功能，也可在下方查詢列自訂問題。",
    selector: ".dock-chips",
    fallbackSelector: ".dock",
  },
  {
    icon: "brain",
    title: "查詢列",
    body: "在此輸入研究問題，按 Enter 或右側送出按鈕開始分析。支援自然語言，例如「台積電 2026Q1 毛利率重點」。",
    selector: ".dock-input",
    fallbackSelector: ".dock",
  },
  {
    icon: "spark",
    title: "執行範例分析",
    body: "接下來示範分析結果的各區塊。點擊下方按鈕執行範例查詢。",
    selector: ".dock",
    fallbackSelector: ".dock",
    isAction: true,
  },
  {
    icon: "layers",
    title: "營運重點摘要",
    body: "每條摘要都有引用 chip（如「法說 p.7」），點擊即可查看原始段落。結論可溯源。",
    selector: ".rcol-main .panel",
    fallbackSelector: ".rcol-main",
  },
  {
    icon: "brain",
    title: "模型思考追蹤",
    body: "AI 的 ReAct 推理步驟（THINK → ACT → OBS）逐步顯示於此，讓您完整了解答案如何生成。",
    selector: ".rcol-ctx .ctx-panel:nth-child(2)",
    fallbackSelector: ".rcol-ctx .ctx-panel:first-of-type",
  },
  {
    icon: "alert",
    title: "監控系統警示",
    body: "系統偵測本次研究相關的異常訊號（如每季財報差異等），觸發後即顯示於此。無異常時顯示「未發現異常訊號」。",
    selector: ".rcol-ctx .ctx-panel:nth-child(3)",
    fallbackSelector: ".rcol-ctx .ctx-panel:nth-of-type(2)",
  },
  {
    icon: "quote",
    title: "引用追蹤器",
    body: "本次研究所有引用來源彙整於此，點擊任一條可開啟原始文件。確保每筆結論有據可查、非投資建議。",
    selector: ".rcol-ctx .ctx-panel:nth-child(4)",
    fallbackSelector: ".rcol-ctx .ctx-panel:last-of-type",
  },
  {
    icon: "panelLeft",
    title: "側欄收縮",
    body: "（桌機版）頁面有兩個可收縮側欄：右側「收起側欄」收合分析面板；左上角面板圖示收合導覽列，讓主要內容獲得更大空間。手機版不支援收縮，導覽改為底部欄位，分析面板改為垂直捲動排列。",
    selector: ".ctx-toggle-btn",
    fallbackSelector: ".mobnav",
    secondarySelector: ".collapse-btn",
  },
  {
    icon: "check",
    title: "引導完成",
    body: "您已了解研究助理的核心功能！有任何疑問，可至說明中心（/help）查看功能說明。",
    selector: null,
    fallbackSelector: null,
    isEnd: true,
  },
];

const LAST_IDX = STEPS.length - 1;

function isVisible(el: Element): boolean {
  const style = window.getComputedStyle(el as HTMLElement);
  if (style.display === "none" || style.visibility === "hidden") return false;
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function applyHighlight(selector: string | null, fallback: string | null, secondary?: string | null) {
  clearHighlight();

  const target = selector ? document.querySelector(selector) : null;
  const el = (target && isVisible(target))
    ? target
    : (fallback ? document.querySelector(fallback) : null);

  if (!el) return;

  (el as HTMLElement).classList.add("tour-highlight");

  // 副元素高亮（如同時標示兩個收縮按鈕）
  if (secondary) {
    const el2 = document.querySelector(secondary);
    if (el2 && isVisible(el2)) (el2 as HTMLElement).classList.add("tour-highlight");
  }

  // Desktop: rcol-ctx 是 overflow:hidden sticky，暫時解除裁切讓第 3 個 panel 可見
  const ctx = document.querySelector(".rcol-ctx");
  if (ctx && el.closest(".rcol-ctx")) {
    (ctx as HTMLElement).classList.add("tour-ctx-open");
  } else if (ctx) {
    (ctx as HTMLElement).classList.remove("tour-ctx-open");
  }

  // 捲動至元素（對 mobile static 佈局有效；overlay 擋住手動捲動但 JS 捲動正常）
  requestAnimationFrame(() => {
    (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

function clearHighlight() {
  document.querySelectorAll(".tour-highlight").forEach((el) =>
    el.classList.remove("tour-highlight")
  );
  const ctx = document.querySelector(".rcol-ctx");
  if (ctx) (ctx as HTMLElement).classList.remove("tour-ctx-open");
}

export interface ResearchTourProps {
  onRunSample: () => void;
  onReset: () => void;
  hasResults: boolean;
}

export function ResearchTour({ onRunSample, onReset, hasResults }: ResearchTourProps) {
  const [open, setOpen]               = useState(false);
  const [step, setStep]               = useState(0);
  const [waiting, setWaiting]         = useState(false);
  const [timedOut, setTimedOut]       = useState(false);

  // refs 不觸發 re-render，供 async 回呼安全讀取
  const waitingRef   = useRef(false);
  const openRef      = useRef(false);
  const timeoutRef   = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── 啟動邏輯：等 OnboardingModal 關閉後再開 Tour ──────────────
  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY)) return;  // 已導覽過，不顯示

    const startTour = () => {
      if (!localStorage.getItem(STORAGE_KEY)) {
        openRef.current = true;
        setOpen(true);
      }
    };

    if (localStorage.getItem(ONBOARD_KEY)) {
      // OnboardingModal 已關閉：延遲 700ms 啟動
      const t = setTimeout(startTour, 700);
      return () => clearTimeout(t);
    } else {
      // OnboardingModal 尚未關閉：等待其 dispatch 的 CustomEvent
      const handler = () => setTimeout(startTour, 400);
      window.addEventListener("polaris:onboarded", handler);
      return () => window.removeEventListener("polaris:onboarded", handler);
    }
  }, []);

  // ── 步驟切換時更新高亮 ───────────────────────────────────────
  useEffect(() => {
    if (!open || waiting) return;
    applyHighlight(STEPS[step].selector, STEPS[step].fallbackSelector, STEPS[step].secondarySelector);
  }, [open, step, waiting]);

  // ── 等待結果：hasResults 變 true 時自動推進 ───────────────────
  // Fix Bug 1/3: useEffect 只在 hasResults 改變時跑，若初始值已是 true
  // 則 handleRunSample 會直接跳步，不進此路徑，無需擔心。
  useEffect(() => {
    if (!waitingRef.current || !hasResults) return;
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    waitingRef.current = false;
    setTimedOut(false);
    setWaiting(false);
    setStep(3);
  }, [hasResults]);

  // ── 卸載清理 ─────────────────────────────────────────────────
  useEffect(() => () => {
    clearHighlight();
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
  }, []);

  if (!open) return null;

  const cur = STEPS[step];

  // ── dismiss：關閉 Tour，僅在未等待 API 時重置頁面 ─────────────
  // Fix Bug 4: waiting=true 代表 API 還在飛行中，此時呼叫 onReset()
  // 會與 run() 的 async 回呼衝突，改為只關閉 Tour，讓頁面自然完成。
  const dismiss = () => {
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    waitingRef.current = false;
    openRef.current = false;
    localStorage.setItem(STORAGE_KEY, "1");
    clearHighlight();
    setOpen(false);
    if (!waiting) onReset();
  };

  const goTo = (idx: number) => {
    if (idx < 0 || idx > LAST_IDX) return;
    setStep(idx);
  };

  // ── 執行範例分析 ──────────────────────────────────────────────
  const handleRunSample = () => {
    // Fix Bug 1+3: 已有結果（包含返回動作步驟的情境）→ 直接跳步，不進 loading
    if (hasResults) {
      setStep(3);
      return;
    }
    onRunSample();
    waitingRef.current = true;
    setWaiting(true);
    setTimedOut(false);
    clearHighlight();

    // Fix Bug 2: 30s 安全逾時，顯示錯誤提示讓使用者仍可繼續
    timeoutRef.current = setTimeout(() => {
      if (waitingRef.current) setTimedOut(true);
    }, LOADING_TIMEOUT_MS);
  };

  // 逾時後強制推進（即使沒有結果也能繼續看說明）
  const forceAdvance = () => {
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    waitingRef.current = false;
    setTimedOut(false);
    setWaiting(false);
    setStep(3);
  };

  return (
    <>
      <div className="tour-overlay" />

      <div className="tour-card">
        {/* Loading 中間態 */}
        {waiting ? (
          <div className="tour-card-loading" style={{ minHeight: 64 }}>
            {timedOut ? (
              <>
                <Icon name="alert" size={16} style={{ color: "rgb(var(--warning))", flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 13 }}>載入時間較長，可繼續查看後續說明。</span>
                <button className="btn primary" style={{ fontSize: 12, flexShrink: 0 }} onClick={forceAdvance}>
                  繼續
                </button>
              </>
            ) : (
              <>
                <Icon
                  name="refresh"
                  size={16}
                  style={{ color: "rgb(var(--primary))", flexShrink: 0, animation: "sl-spin 1s linear infinite" }}
                />
                <span style={{ flex: 1 }}>分析中，請稍候…</span>
                <button
                  className="btn ghost"
                  style={{ fontSize: 12, color: "rgb(var(--muted))", flexShrink: 0 }}
                  onClick={dismiss}
                >
                  跳過
                </button>
              </>
            )}
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="tour-card-head">
              <div className="tour-card-icon">
                <Icon name={cur.icon} size={16} />
              </div>
              <span className="tour-card-title">{cur.title}</span>
              <span className="tour-card-counter">
                {cur.isEnd ? "完成" : `步驟 ${step + 1} / ${LAST_IDX}`}
              </span>
            </div>

            {/* Body */}
            <div className="tour-card-body">{cur.body}</div>

            {/* Footer */}
            <div className="tour-card-footer">
              {/* Step dots（不含結尾卡） */}
              <div className="tour-dots">
                {STEPS.slice(0, LAST_IDX).map((_, i) => (
                  <button
                    key={i}
                    aria-label={`步驟 ${i + 1}`}
                    className={
                      "tour-dot " +
                      (i === step ? "active" : i < step ? "done" : "pending")
                    }
                    onClick={() => goTo(i)}
                  />
                ))}
              </div>

              {/* Navigation */}
              <div className="tour-actions">
                {step > 0 && !cur.isEnd && (
                  <button className="btn ghost" style={{ fontSize: 13 }} onClick={() => goTo(step - 1)}>
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

                {cur.isEnd ? (
                  <button className="btn primary" style={{ fontSize: 13 }} onClick={dismiss}>
                    完成
                    <Icon name="check" size={14} />
                  </button>
                ) : cur.isAction ? (
                  // Fix Bug 1+3: hasResults 已有值時，改為「查看結果」直接跳步
                  hasResults ? (
                    <button className="btn primary" style={{ fontSize: 13 }} onClick={() => setStep(3)}>
                      查看結果
                      <Icon name="arrowRight" size={14} />
                    </button>
                  ) : (
                    <button className="tour-sample-btn" onClick={handleRunSample}>
                      執行範例分析
                      <Icon name="arrowRight" size={14} />
                    </button>
                  )
                ) : (
                  <button className="btn primary" style={{ fontSize: 13 }} onClick={() => goTo(step + 1)}>
                    下一步
                    <Icon name="arrowRight" size={14} />
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
