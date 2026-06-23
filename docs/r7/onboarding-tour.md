# ResearchTour — 設計規格與修改歷史

> 維護：R7
> 合併自：`frontend/onboarding-tour.md`、`frontend/onboarding-tour-bugfix.md`
> 實作檔案：`frontend/src/components/polaris/ResearchTour.tsx`

---

## 設計規格（已確認）

> 整理日期：2026-06-19

**範圍**：`/research` 頁初次進入的逐步功能引導。
**方向**：底部固定引導卡 + 目標元素高亮（方向 A），無外部套件。
**觸發 flag**：`localStorage('polaris-research-toured')`（設值後不再顯示）

### 已確認決策

| 項目 | 決策 |
|---|---|
| 遮罩點擊穿透 | **否**，`pointer-events: all`，Tour 期間使用者只能操作引導卡 |
| 元素尚未出現時 | **引導執行範例分析**：Step 3 引導卡提供「執行範例分析」按鈕 |
| KPI 指標卡步驟 | **移除**：後端永遠回傳 `kpis: []`，元素不保證出現 |
| 結束後狀態 | **重置頁面初始值**：完成或跳過時 ResearchPage 清除查詢與結果 |
| 說明頁再次觀看入口 | **不加** |

### 與 OnboardingModal 分工

| 元件 | 觸發時機 | 作用 |
|---|---|---|
| `OnboardingModal` | 初次進入任何 dashboard 頁 | 整體功能 macro 概覽（4 步） |
| `ResearchTour` | 初次進入 `/research`，延遲 700ms | 研究頁 UI 逐一說明（9 步含 loading） |

### UX 佈局

```
┌──────────────────────────── main ────────────────────────────┐
│  ░░░░░░░░░ 半透明遮罩（pointer-events:all，z-index 200）░░░░░  │
│                                                               │
│         ┌─────────────────────────────────┐                  │
│         │  高亮元素（z-index 201）          │                  │
│         │  ring 發光 + pulse 動畫           │                  │
│         └─────────────────────────────────┘                  │
├───────────────────────────────────────────────────────────────┤
│  dock（固定底部）                                               │
└───────────────────────────────────────────────────────────────┘

┌──────── Tour 引導卡（z-index 202，浮在 dock 上方）──────────────┐
│  💡 步驟 2 / 9   ● ● ○ ○ ○ ○ ○ ○ ○                              │
│  這是查詢列。輸入股票研究問題後按 Enter 或右側送出按鈕。              │
│                                        [← 上一步]  [下一步 →]  │
└───────────────────────────────────────────────────────────────┘
```

### 步驟設計（最終 9 步）

| idx | 標題 | selector | secondarySelector | fallbackSelector |
|---|---|---|---|---|
| 0 | 快速開始 | `.dock-chips` | — | `.dock` |
| 1 | 查詢列 | `.dock-input` | — | `.dock` |
| 2 | 執行範例分析（動作） | `.dock` | — | `.dock` |
| 3 | 營運重點摘要 | `.rcol-main .panel` | — | `.rcol-main` |
| 4 | 模型思考追蹤 | `.rcol-ctx .ctx-panel:nth-child(2)` | — | `…:first-of-type` |
| 5 | 監控系統警示 | `.rcol-ctx .ctx-panel:nth-child(3)` | — | `…:nth-of-type(2)` |
| 6 | 引用追蹤器 | `.rcol-ctx .ctx-panel:nth-child(4)` | — | `…:last-of-type` |
| 7 | 側欄收縮 | `.ctx-toggle-btn` | `.collapse-btn` | `.mobnav` |
| 8 | 引導完成（結尾） | null | — | — |

> **rcol-ctx 子元素順序（影響 nth-child）**：
> 1. `button.ctx-toggle-btn`、2. `div.ctx-panel`（思考追蹤）、3. `div.ctx-panel`（監控警示）、4. `div.ctx-panel`（引用追蹤）

### 元件 API

```tsx
interface ResearchTourProps {
  onRunSample: () => void;   // Step 2 → ResearchPage 執行 run()
  onReset: () => void;       // 完成/跳過 → ResearchPage 清除查詢與結果
  hasResults: boolean;       // displayData !== undefined，用於從 loading 推進
}
```

### 高亮 CSS

```css
.tour-overlay { position:fixed; inset:0; background:rgb(0 0 0/.4); z-index:200; pointer-events:all; }
.tour-highlight { position:relative; z-index:201; border-radius:10px;
  box-shadow: 0 0 0 3px rgb(var(--primary)), 0 0 20px 4px rgb(var(--primary)/.3);
  animation: tour-pulse 1.8s ease-in-out infinite; }
@keyframes tour-pulse {
  0%,100% { box-shadow:0 0 0 3px rgb(var(--primary)), 0 0 20px 4px rgb(var(--primary)/.3); }
  50%      { box-shadow:0 0 0 4px rgb(var(--primary)), 0 0 28px 8px rgb(var(--primary)/.15); }
}
.rcol-ctx.tour-ctx-open { overflow: visible; }
@media (max-width:1230px) {
  .tour-card { bottom:196px; width:min(520px,96vw); }
  .tour-card .btn { min-height:32px; font-size:12.5px; padding:5px 10px; }
}
@media (max-width:560px) { .tour-card { bottom:188px; } }
```

---

## 修改歷史

### 2026-06-19 — Bug 修復批次

**影響檔案**：`ResearchTour.tsx`、`OnboardingModal.tsx`、`polaris.css`

#### Bug 1 + 3（Critical）— loading 永遠不推進

**根因**：`useEffect` 只在 `hasResults` 改變時觸發；若初始值已是 `true` 或從 Step 3+ 退回 Step 2，effect 不跑。

**修法**：`handleRunSample` 點擊時先同步檢查 `hasResults`
```ts
if (hasResults) { setStep(3); return; }
```

#### Bug 2（Critical）— API 失敗時 loading 永遠不解除

**修法**：加 30 秒安全逾時，到期後顯示「繼續」強制推進
```ts
timeoutRef.current = setTimeout(() => { if (waitingRef.current) setTimedOut(true); }, 30_000);
```

#### Bug 4（Medium）— dismiss() 在 API 飛行中呼叫 onReset()

**修法**：`waiting=true` 時跳過 `onReset()`
```ts
if (!waiting) onReset();
```

#### Bug 5（Medium）— OnboardingModal 與 ResearchTour 同時出現

**修法**：OnboardingModal 關閉時 dispatch CustomEvent；Tour 等事件後再啟動
```ts
// OnboardingModal.tsx
window.dispatchEvent(new CustomEvent("polaris:onboarded"));
// ResearchTour.tsx
window.addEventListener("polaris:onboarded", handler);
```

#### Bug 7（UX）— Desktop 引用追蹤器被 overflow:hidden 裁切

**修法**：高亮目標在 `.rcol-ctx` 內時，暫時加 `.tour-ctx-open` class 解除裁切

#### Bug 8（UX）— Mobile 部分面板看不到

**修法**：`applyHighlight()` 後加 `scrollIntoView({ behavior: "smooth", block: "center" })`

#### Bug 9（Layout）— Mobile tour-card 被 mobnav 遮住

**修法**：`@media (max-width:1230px) { .tour-card { bottom: 196px; } }`

#### Bug 10 + 11（UX）— selector 選到錯誤面板

**根因**：原用 `:first-child`/`:nth-child(3)` 計算錯誤（未計 `button.ctx-toggle-btn`）

**修法**：模型思考追蹤改 `:nth-child(2)`；引用追蹤器改 `:nth-child(4)`

#### Feature — 新增監控系統警示（idx=5）+ 側欄收縮（idx=7）步驟

新增 `secondarySelector` 欄位，支援雙元素同時高亮

---

### 2026-06-20 — RWD + UI 追加改動

#### Bug 12（RWD）— Tour Card 手機版按鈕過大

**修法**：新增 `≤1230px` + `≤560px` media query，覆蓋全域 `min-height: 44px`

#### RWD 全站整體縮小

- `body { font-size: 16px }` 於 `≤1230px`；`14.5px` 於 `≤560px`
- `peer-toolbar` 手機版 `flex-direction: column; align-items: stretch`

#### Feature — 深淺色主題切換動畫（View Transition + Sparkle）

抽取 `useThemeToggle` hook，封裝放射展開 + 8 顆星粒子，三處主題切換按鈕共用。

#### Feature — 對話紀錄刪除按鈕 + 確認卡片

每個 history item 從整列 `<button>` 改為外層 `<div onClick=navigate>` + 獨立 `<button class="history-del">`。

#### Feature — 手機底部導覽「更多」Drawer

5 格 mobnav 改為 4 格 + 「更多」slide-up drawer，容納 8 個 dashboard 頁面。

---

## DoD（最終）

- [x] 9 步驟（含 loading 中間態）行為正確
- [x] Bug 1–12 全數修正
- [x] `secondarySelector` 支援雙元素高亮
- [x] 手機版 fallback 高亮 `.mobnav`；說明文字標示桌機限定
- [x] RWD 全站縮小完成
- [x] 後端零異動
