# Polaris Desk — 前端動畫索引

> 整理日期：2026-06-18｜維護：R7
> 動畫分三層：純 CSS keyframe / transition（GPU compositing）、短暫 rAF loop（自動停止）、framer-motion（Aceternity UI 互動效果，少量使用）。

---

## Keyframes 總覽

| Keyframe | 定義位置 | 用途 |
|---|---|---|
| `magic-shimmer` | `polaris.css` | hover 單次掃光（lp-feat card） |
| `magic-shimmer-loop` | `polaris.css` | 持續循環掃光（lp-card、CTA 按鈕、dock focus） |
| `accent-flow` | `polaris.css` | 首頁 hero 漸層文字流動 |
| `sk-shimmer` | `polaris.css` | Skeleton loading 掃光 |
| `rs-beam-fall` | `polaris.css` | ReAct trace 進行中步驟光點下落 |
| `aurora-scan` | `polaris.css` | 首頁 hero 光帶橫掃 |
| `star-rotate` | `polaris.css` | Brand star icon 持續旋轉 |
| `float-bob` | `polaris.css` | 首頁 lp-float 卡片上下浮動 |
| `badge-pulse` | `polaris.css` | nav 通知角標 outline + scale 脈動 |
| `alert-enter` | `polaris.css` | 警示 / 對話紀錄列表滑入（共用） |
| `news-row-enter` | `polaris.css` | 新聞列表項目滑入 |
| `win-glow` | `polaris.css` | PeerKpi 勝出值文字發光（需 `.pk-val.win` class） |

---

## 環境裝飾（Ambient）

### Dot Matrix 點陣背景
- **位置**：`.lp-hero`
- **實作**：`background-image: radial-gradient(...)` 26×26px 重複點陣 + 橢圓 vignette 遮罩
- **透明度**：`rgb(var(--foreground) / .11)`

### Aurora Scan 光帶掃描
- **位置**：`.lp-hero::before`
- **動畫**：`aurora-scan 12s ease-in-out infinite`
- **行為**：38% 寬光帶從左掃到右（270%），在右側停留 58% 時間，產生自然間歇感
- **顏色**：`rgb(255 255 255 / .10–.18)`（白光；曾試過 primary 色，視覺上不如白光乾淨，已還原）

### Brand Star 旋轉
- **位置**：`.brand-star svg`
- **動畫**：`star-rotate 22s linear infinite`
- **注意**：作用在 `svg` 而非外層容器（容器是圓角方塊，旋轉會露圓角）

### lp-float 浮動
- **位置**：`.lp-float`
- **動畫**：`float-bob 3.2s ease-in-out infinite`，振幅 7px

---

## 互動效果（Interaction）

### Border Beam Shimmer

| 元素 | 觸發 | Keyframe | 時長 |
|---|---|---|---|
| `.lp-feat` card | hover | `magic-shimmer 0.65s ease forwards` | 單次 |
| `.lp-card` 模擬視窗 | 持續 | `magic-shimmer-loop 5s ease infinite` | 循環 |
| `.btn.primary.xl` CTA 按鈕 | 持續 | `magic-shimmer-loop 4s ease infinite` | 循環 |
| `.dock-row` | focus-within | `magic-shimmer-loop 5s ease infinite` | 循環 |

**`magic-shimmer-loop` 技巧**：20% 動畫本體（`-130%` → `130%`），剩餘 80% 停在畫面外，產生自然停頓間隔而不是連續閃爍。

### Animated Gradient Text
- **位置**：`.lp-h1 .accent`
- **動畫**：`accent-flow 5s ease infinite`，`background-size: 300% auto`
- **注意**：需要 `-webkit-background-clip: text` + `-webkit-text-fill-color: transparent`

---

## 進入動畫（Entrance / Stagger）

### Alert / 對話紀錄 滑入
- **Keyframe**：`alert-enter`（`translateX(32px) → 0`，`opacity: 0 → 1`）
- **時長**：`0.42s cubic-bezier(.22,1,.36,1)`（spring 感）
- **使用者**：`.alert`（nth-child 1–5，delay 0–280ms）、`.history-item`（per-group stagger，45ms 間隔）

### 新聞列表 滑入
- **Keyframe**：`news-row-enter`（`translateX(24px) → 0`）
- **時長**：`0.4s cubic-bezier(.22,1,.36,1)`
- **Stagger**：`animationDelay: i * 45ms`（切 tab 時重播）

---

## 狀態動畫（State）

### Skeleton Shimmer
- **位置**：`.sk::after`
- **Keyframe**：`sk-shimmer`（`translateX(-100%) → translateX(100%)`）
- **白色掃光**：`rgb(255 255 255 / .45)`（深色模式修正，不用 `--background` 會比 border 更暗）

### ReAct Trace Beam
- **位置**：`.react-step.active .rs-bar::after`
- **Keyframe**：`rs-beam-fall`（`top: -35% → 120%`）
- **注意**：光點在 3px `.rs-bar` 內部移動，避免被 `.react-list overflow-y: auto` 裁切

### Badge Pulse
- **位置**：`.nav-badge`
- **Keyframe**：`badge-pulse`（`scale(1) → scale(1.12)` + `outline` 擴張）
- **修正原因**：`.nav-badge` 有 `overflow: hidden`（sidebar 收縮動畫需要），`box-shadow` 會被裁切，改用 `outline`（不受 overflow 影響）

---

## Framer Motion 動畫（Aceternity UI）

> 依賴：`framer-motion`（已安裝）。原則：少量使用，只套用高視覺影響、低風險的元件。

### SpotlightCard / SpotlightButton
- **檔案**：`frontend/src/components/ui/SpotlightCard.tsx`
- **使用位置**：首頁 `.lp-feat` 功能卡（`SpotlightCard`）、研究 / 同業頁 KPI cards（`SpotlightButton`）
- **行為**：滑鼠在 card 上移動時，一道 280–320px radial gradient 光暈跟隨游標；離開時 0.25s 淡出
- **實作關鍵**：用 `useMotionTemplate` 即時產生 gradient 字串；hover 狀態以 `onMouseEnter/Leave` 追蹤（不用 `whileHover`，因為 overlay 有 `pointer-events: none` 無法自行偵測 hover）
- **顏色**：`rgb(var(--primary) / .13)`，不蓋過既有 card 背景

### TextGenerate
- **檔案**：`frontend/src/components/ui/TextGenerate.tsx`
- **使用位置**：研究頁「營運重點摘要」每條文字
- **行為**：查詢完成後，每個詞依序從右（`x: 12`）滑入並淡入；每條摘要延遲 80ms stagger
- **Easing**：`easeOut`，0.28s per word；單條最大累計 delay 0.8s（`Math.min`）
- **重播機制**：`key={s.text}` 確保新查詢結果 unmount / remount，動畫重播
- **方向**：`x: 12 → 0`（與 alert-enter、news-row-enter 一致，從右往左）

---

## JS 動畫（requestAnimationFrame）

### Number Ticker（首頁 Hero Stats）
- **元件**：`NumberTicker`（`frontend/src/app/page.tsx`）
- **觸發**：`IntersectionObserver`，進入 viewport（threshold 0.5）後啟動
- **Easing**：ease-out-cubic（`1 - (1-t)^3`）
- **時長**：1400ms
- **支援**：`suffix`、`decimals`、`delay`、自訂 `formatter`

### Number Ticker（KPI Cards）
- **元件**：`AnimatedNumber`（`frontend/src/components/polaris/KpiCard.tsx`）
- **觸發**：component mount（研究完成後 KPI 卡出現）
- **Easing**：ease-out-cubic，900ms
- **自動偵測**：`raw.indexOf(".")` 推算小數位數，非數字則直接顯示原始字串

---

## CSS Transition（非 Keyframe）

| 元素 | 屬性 | 時長 / Easing |
|---|---|---|
| `.dv-overlay` 遮罩 | `background` | `0.25s ease` |
| `.dv-sheet` 側欄 | `transform` | `0.35s cubic-bezier(.22,1,.36,1)` |
| `.research-layout` | `grid-template-columns` | `0.22s ease` |
| `.app`（rail collapse） | `grid-template-columns` | `0.22s ease` |
| `.brand-name`, `.nav-item span` | `opacity`, `max-width` | `0.15s / 0.22s ease` |

---

## 已移除的效果

| 效果 | 移除原因 |
|---|---|
| Progress bar shimmer | 進度條高度 5px 過細，效果不可見 |
| ComplianceBanner entrance | 只在查詢完成後出現一次，播完即逝，使用者難以察覺 |
| Citation chip hover | 使用者回饋去除 |

---

## 效能備注

- 所有 CSS keyframe 動畫均作用於 `transform` / `opacity`，瀏覽器自動提升至 GPU compositing layer，不觸發 layout / paint
- `backdrop-filter: blur()` 是唯一較重的屬性，僅用於 `.lp-nav`（sticky header）
- `requestAnimationFrame` loop 均在動畫結束後停止，無持續 JS 計算開銷
- **framer-motion**：`useMotionValue` + `useMotionTemplate` 在 rAF 內執行，不觸發 React re-render；每個 SpotlightCard 獨立維護 motion value，複數卡片同時 hover 無互相干擾
