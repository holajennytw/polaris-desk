# 研究頁引導 Tour — 設計規格（已確認）

> **範圍**：`/research` 頁初次進入的逐步功能引導。
> **方向**：底部固定引導卡 + 目標元素高亮（方向 A），無外部套件。
> **實作檔案**：`frontend/src/components/polaris/ResearchTour.tsx`
> **觸發 flag**：`localStorage('polaris-research-toured')`（設值後不再顯示）
> **變更歷史**：Bug fix log → [`onboarding-tour-bugfix.md`](./onboarding-tour-bugfix.md)

---

## 已確認決策

| 項目 | 決策 |
|---|---|
| 遮罩點擊穿透 | **否**，`pointer-events: all`，Tour 期間使用者只能操作引導卡 |
| 元素尚未出現時 | **引導執行範例分析**：Step 3 引導卡提供「執行範例分析」按鈕，結果出現後繼續 |
| KPI 指標卡步驟 | **移除**：`/research` 後端永遠回傳 `kpis: []`，`/financials` 依賴未入庫的 `financial_metrics`，元素不保證出現 |
| 結束後狀態 | **重置頁面初始值**：完成或跳過時 ResearchPage 清除查詢與結果 |
| 說明頁再次觀看入口 | **不加** |

---

## 與現有 OnboardingModal 的分工

| 元件 | 觸發時機 | 作用 |
|---|---|---|
| `OnboardingModal` | 初次進入任何 dashboard 頁 | 整體功能 macro 概覽（4 步） |
| `ResearchTour`（本件） | 初次進入 `/research`，延遲 700ms 後啟動 | 研究頁 UI 逐一說明（9 步含 loading） |

---

## UX 佈局

```
┌────────────────────────── main ──────────────────────────────┐
│  ░░░░░░░░░ 半透明遮罩（pointer-events:all，z-index 200）░░░░░  │
│                                                               │
│         ┌─────────────────────────────────┐                  │
│         │  高亮元素（z-index 201）          │  ← tour-highlight │
│         │  ring 發光 + pulse 動畫           │                  │
│         └─────────────────────────────────┘                  │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│  dock（固定底部）                                               │
└───────────────────────────────────────────────────────────────┘

┌──────── Tour 引導卡（z-index 202，浮在 dock 上方）──────────────┐
│  💡 步驟 2 / 9   ● ● ○ ○ ○ ○ ○ ○ ○                              │
│  這是查詢列。輸入股票研究問題後按 Enter 或右側送出按鈕。              │
│                                        [← 上一步]  [下一步 →]  │
└───────────────────────────────────────────────────────────────┘
```

**卡片定位**：`position: fixed; bottom: 132px; left: 50%; transform: translateX(-50%)`
（dock ≈ 120px + 12px gap；卡片寬度 `min(520px, 92vw)`）

---

## 高亮 CSS（加入 polaris.css）

```css
.tour-overlay {
  position: fixed;
  inset: 0;
  background: rgb(0 0 0 / 0.4);
  z-index: 200;
  pointer-events: all;
}

.tour-highlight {
  position: relative;
  z-index: 201;
  border-radius: 10px;
  box-shadow: 0 0 0 3px rgb(var(--primary)),
              0 0 20px 4px rgb(var(--primary) / 0.3);
  animation: tour-pulse 1.8s ease-in-out infinite;
}

@keyframes tour-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgb(var(--primary)),
                          0 0 20px 4px rgb(var(--primary) / 0.3); }
  50%       { box-shadow: 0 0 0 4px rgb(var(--primary)),
                          0 0 28px 8px rgb(var(--primary) / 0.15); }
}
```

---

## 步驟設計（9 步）

> **rcol-ctx 子元素順序**（影響 nth-child 計算）：
> 1. `button.ctx-toggle-btn`（收縮按鈕）
> 2. `div.ctx-panel`（模型思考追蹤）
> 3. `div.ctx-panel`（監控系統警示）
> 4. `div.ctx-panel`（引用追蹤器）

### Phase 1 — 不需查詢結果（idx 0–2）

| idx | 類型 | selector | 標題 | 說明 |
|---|---|---|---|---|
| 0 | 說明 | `.dock-chips` | 快速開始 | 點選預設問題可快速體驗，也可在下方查詢列自訂問題。 |
| 1 | 說明 | `.dock-input` | 查詢列 | 輸入股票研究問題，按 Enter 或右側送出按鈕開始分析。支援自然語言，例如「台積電 2026Q1 毛利率重點」。 |
| 2 | **動作** | `.dock` | 執行範例分析 | 接下來示範分析結果的各區塊功能。點擊下方按鈕執行範例查詢，結果出現後繼續引導。 |

Step 2（idx=2）的引導卡底部顯示「執行範例分析 →」按鈕，取代「下一步」。
點擊後：`onRunSample()` + `setWaiting(true)` → 顯示 loading 狀態。

### Transition — Loading（等待後端回傳）

卡片切換為「分析中，請稍候…」+ spinner。
`hasResults` 由 `false → true` 時自動推進至 idx=3。

### Phase 2 — 需要查詢結果（idx 3–8）

| idx | 類型 | selector | secondarySelector | fallbackSelector | 標題 | 備註 |
|---|---|---|---|---|---|---|
| 3 | 說明 | `.rcol-main .panel` | — | `.rcol-main` | 營運重點摘要 | |
| 4 | 說明 | `.rcol-ctx .ctx-panel:nth-child(2)` | — | `.rcol-ctx .ctx-panel:first-of-type` | 模型思考追蹤 | nth-child(2)：第 1 個 ctx-panel |
| 5 | 說明 | `.rcol-ctx .ctx-panel:nth-child(3)` | — | `.rcol-ctx .ctx-panel:nth-of-type(2)` | 監控系統警示 | nth-child(3)：第 2 個 ctx-panel |
| 6 | 說明 | `.rcol-ctx .ctx-panel:nth-child(4)` | — | `.rcol-ctx .ctx-panel:last-of-type` | 引用追蹤器 | nth-child(4)：第 3 個 ctx-panel |
| 7 | 說明 | `.ctx-toggle-btn` | `.collapse-btn` | `.mobnav` | 側欄收縮 | 桌機：同時高亮右側收縮鈕＋左上收縮鈕；手機：fallback 高亮底部導覽列 |
| 8 | **結尾** | null | — | — | 引導完成 🎉 | 清除所有高亮 |

---

## 元件 API

```tsx
interface ResearchTourProps {
  onRunSample: () => void;   // Step 2 按「執行範例分析」→ ResearchPage 執行 run()
  onReset: () => void;       // 完成/跳過 → ResearchPage 清除查詢與結果
  hasResults: boolean;       // displayData !== undefined，用於從 loading 推進
}
```

**State**：
- `open: boolean`
- `step: number`（0–8）
- `waiting: boolean`（loading 中間態）
- `timedOut: boolean`（30s 逾時安全閥）

---

## ResearchPage 整合

```tsx
const handleTourRunSample = () => {
  const sample = "台積電 2026Q1 法說會重點";
  setQuery(sample);
  run(sample);
};

const handleTourReset = () => {
  setQuery("");
  setHasQueried(false);
  setPhase("idle");
  setProgress(0);
  setRestoredData(undefined);
  setRestoredAt(null);
  contraAlertStore.clear();
};

// JSX 最尾端插入：
<ResearchTour
  onRunSample={handleTourRunSample}
  onReset={handleTourReset}
  hasResults={!!displayData}
/>
```

---

## 互動流程

```
進入 /research → 延遲 700ms
    │
    ├─ polaris-research-toured 存在 → 不顯示
    └─ 否 → open=true, step=0

step 0–1：說明步驟
    ├─ 上一步 / 下一步 / 點步驟點 → 切換
    └─ 跳過 → dismiss()

step 2：動作步驟
    └─ 「執行範例分析」→ onRunSample() + waiting=true → loading 卡

loading：
    └─ hasResults 變 true → waiting=false, step=3

step 3–7：說明步驟（同 0–1）
    └─ step 7（側欄收縮）：同時高亮 .ctx-toggle-btn + .collapse-btn（secondarySelector）
                           手機 fallback：高亮 .mobnav

step 8：結尾
    └─ 「完成」→ dismiss()

dismiss()：
    ├─ localStorage.setItem('polaris-research-toured', '1')
    ├─ 移除所有 .tour-highlight
    ├─ setOpen(false)
    └─ onReset()
```

---

## DoD

- [x] `ResearchTour.tsx` 建立，props 介面正確
- [x] 9 步驟（含 loading 中間態）行為正確
- [x] `.tour-overlay`、`.tour-highlight` CSS 加入 `polaris.css`
- [x] 首次進入 `/research` 延遲 700ms 啟動，完成後不再顯示
- [x] `hasResults` 變 true 時自動從 loading 推進至 idx=3
- [x] dismiss 後呼叫 `onReset()`，頁面回到空白初始值
- [x] 元素不存在時降級高亮父容器（fallbackSelector），不報錯
- [x] `secondarySelector` 同時高亮第二個元素（側欄收縮步驟）
- [x] 手機版 fallback 高亮 `.mobnav`；說明文字標示桌機版限定
- [x] RWD（< 1230px）selector 仍有效
