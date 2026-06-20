# Polaris Desk — Design System

> 整理日期：2026-06-18｜維護：R7
> 本文件為前端 CSS 設計規範的單一事實來源。修改 `polaris.css` 時同步更新此文件。

---

## Breakpoints

| 名稱 | 範圍 | 說明 |
|------|------|------|
| `xl` | ≥ 1400px | 大型桌機；sidebar nav 完整顯示 |
| `lg` | 1231–1399px | 中型桌機；sidebar nav 仍可見，字體維持 22px |
| `md` | 1181–1230px | 小型桌機 / 大平板；sidebar 隱藏，切換為 mobnav |
| `sm` | 1180px 以下 | 單欄版型，sidebar content 收合 |
| `xs` | ≤ 560px | 小螢幕，KPI grid 調整為單欄 |

---

## Typography

### Page Title（`.page-title`）

| 屬性 | 值 |
|------|----|
| font-size | **26px** |
| font-weight | 700 |
| font-family | `var(--sans)` |

### Sidebar Nav（`.nav-item`）

| Breakpoint | font-size | 說明 |
|------------|-----------|------|
| ≥ 1400px（xl） | **22px** | 桌機標準 |
| 1231–1399px（lg） | **22px** | 中型桌機同桌機 |
| ≤ 1230px | — | sidebar 隱藏，改用 mobnav |

- `.nav-item span` 繼承父層 22px，不需獨立設定
- `.nav-item.active` 字體同 22px，不另設 override
- `.nav-item svg`：固定 **20×20px**

**mobnav**（底部導覽列，≤ 1230px）

結構：4 個主要 tab + 第 5 格「更多」按鈕（icon: `layers`）

| 位置 | 頁面 |
|------|------|
| tab 1 | 首頁 `/` |
| tab 2 | 研究 `/research` |
| tab 3 | 同業 `/peer` |
| tab 4 | 通知 `/notifications` |
| tab 5 | 更多（觸發 drawer） |

| 元素 | font-size |
|------|-----------|
| `.mobnav-item` label | 14px |
| `.mobnav-item` icon | 20×20px |

### 首頁 Nav（`.lp-nav`）

| 元素 | font-size |
|------|-----------|
| `.lp-nav`（基準） | **22px** |
| `.lp-brand .brand-name` | **22px** |
| `.lp-nav-links a` | **22px** |

### Nav 分類標籤（`.nav-label`）

| 屬性 | 值 |
|------|----|
| font-size | 14px |
| font-weight | 600 |
| letter-spacing | 0.14em |
| text-transform | uppercase |

### 列表頁面字體（新聞 / 對話紀錄 / 通知，共用規範）

四個頁面（`/news`、`/history`、`/notifications`、`/library`）使用統一字體縮放規則：

| 類別 | Class | Desktop | ≤ 1230px | ≤ 560px |
|---|---|---|---|---|
| 新聞標題 | `.ni-title` | **20px / 600** | 17px | 15px |
| 新聞 meta | `.ni-meta` | **16px** | 14px | 13px |
| 對話紀錄標題 | `.history-query` | **20px / 600** | 17px | 15px |
| 對話紀錄 meta | `.history-meta` | **14px** | 13px | 12px |
| 通知標題 | `.alert-title` | **20px / 600** | 17px | 15px |
| 通知內文 | `.alert-sum` | **15px** | 14px | 13px |
| 通知 meta | `.alert-meta` | **16px** | 14px | 13px |

**最小值：任何螢幕尺寸下，列表文字不得小於 12px。**

> **字體統一原則**：`.ni-title`、`.history-query`、`.alert-title` 三者桌機字體均為 **20px / font-weight 600 / line-height 1.45**，確保跨頁視覺一致。
> **font-mono 數字**：`.ni-meta` 與 `.alert-meta` 桌機 **16px**，RWD 遞減至 14 / 13px。

### 空態文字（`.chart-empty`）

| 屬性 | 值 |
|------|----|
| font-size | 16px |
| color | `rgb(var(--muted))` |
| padding | 20px 16px（可被 inline style 覆蓋垂直值） |

---

## Spacing

### Rail Brand（`.rail-brand`）

| 屬性 | 值 |
|------|----|
| height | **72px**（原 58px） |
| padding | `18px 18px` |
| border-bottom | `1px solid rgb(var(--rail-line))` |

### Panel

| 元素 | 值 |
|------|----|
| `.panel-head` padding | `12px 16px` |
| `.panel-body` padding | `16px` |
| `.compliance` margin | `16px 0` |

### Page 寬度

| Class | max-width | 用途 |
|---|---|---|
| `.page` | 1500px | 預設（research、peer 等全寬頁面） |
| `.page.narrow` | **800px** | 單欄列表頁（新聞、對話紀錄、通知、**資料庫**） |

### Touch Targets（≤ 1230px，即 `md` 以下）

**規則：所有可互動功能元素，觸控範圍不得小於 44×44px。**

下列元素在 `@media (max-width: 1230px)` 已強制套用：

| 元素 | 規則 |
|------|------|
| `.btn` | `min-height: 44px` |
| `.icon-btn` | `width: 44px; height: 44px` |
| `.mobnav-item` | `min-height: 44px` |
| `.mob-more-item` | `min-height: 56px`（drawer 內項目，比 mobnav 略高） |
| `.chip` | `min-height: 44px; display: inline-flex; align-items: center` |
| `.news-tab` | `min-height: 44px` |
| `.cpick-btn` | `min-height: 44px` |
| `.cite-item` | `min-height: 44px` |

**新增互動元素清單**：新增任何在 `md` 以下可點擊的元素時，必須同步加入 `min-height: 44px` 規則。

---

## Components

### Brand Star（`.brand-star`）

| 屬性 | 值 |
|------|----|
| 容器尺寸 | **38×38px**（原 30px） |
| icon size | **22px**（原 17px） |
| 背景 | `linear-gradient(150deg, rgb(var(--primary-bright)), rgb(var(--primary)))` |
| border-radius | `var(--radius-icon)` |
| animation | `star-rotate 22s linear infinite`（作用於 `svg`，不在容器） |

### 新聞列表 Icon（`.ni-icon`）

| 屬性 | 值 |
|------|----|
| 容器尺寸 | 32×32px |
| icon size | 17px（CSS override：`.ni-icon svg { width: 17px; height: 17px }`） |
| 背景 | `rgb(var(--primary) / .1)` |
| border-radius | `var(--radius-xs)` |

### 對話紀錄 Icon
使用 `.ni-icon`，與新聞列表完全一致。

### 監控警示 Icon（`.alert-ico`）

用於 `AlertItem` 元件（監控系統警示 / 風險動態），取代原本的 `.tag.high` pill 徽章。

| 屬性 | 值 |
|------|----|
| 容器尺寸 | **32×32px**（與 `.ni-icon` 一致） |
| icon size | 17px（`.alert-ico svg { width: 17px; height: 17px }`） |
| border-radius | `var(--radius-xs)` |
| layout | `display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px` |

| 層級 | Class | 背景 | 文字色 | 圖示 |
|---|---|---|---|---|
| 高風險 | `.alert-ico.high` | `rgb(var(--danger) / .10)` | `rgb(var(--danger))` | `alert`（警告三角） |
| 中風險 | `.alert-ico.mid` | `rgb(var(--warning) / .12)` | `rgb(var(--warning))` | `alert`（警告三角） |
| 資訊 | `.alert-ico.info` | `rgb(var(--info) / .10)` | `rgb(var(--info))` | `bolt` |

**套用位置**：研究助理「監控系統警示」、同業比較「監控系統警示」、通知中心「風險動態」——三處共用同一個 `AlertItem` 元件，樣式自動統一。

**`.alert` 列表佈局**：`display: flex; align-items: flex-start; gap: 13px; padding: 12px 16px;`（與 `.news-row` / `.history-item` 對齊）

### SpotlightCard / SpotlightButton（framer-motion）

- **檔案**：`frontend/src/components/ui/SpotlightCard.tsx`
- **依賴**：`framer-motion`（已安裝）
- **用途**：游標跟隨光暈效果，少量套用於高視覺影響的卡片元件

| 元件 | 底層元素 | 套用位置 |
|---|---|---|
| `SpotlightCard` | `<div>` | 首頁 `.lp-feat` 功能卡 |
| `SpotlightButton` | `<button>` | 研究 / 同業頁 KPI cards |

- 光暈顏色：`rgb(var(--primary) / .13)`
- hover 偵測：`onMouseEnter/Leave` on 父元素（overlay 設 `pointer-events: none`，不可自行偵測）

### TextGenerate（framer-motion）

- **檔案**：`frontend/src/components/ui/TextGenerate.tsx`
- **用途**：文字逐詞從右滑入，模擬 AI 串流輸出感
- **套用位置**：研究頁摘要每條文字（`key={s.text}` 強制查詢變更時重播）
- **方向**：`x: 12 → 0`，與全站滑入動畫方向一致

### 資料庫頁面（`/library`）

#### Tab 結構

仿照對話紀錄（`/history`）的靜態 tab 模式：

| 列 | 說明 | 動態 / 靜態 |
|---|---|---|
| 第一列：文件類型 | `全部｜重大訊息｜法說會逐字稿｜法說會` | **靜態**（`TYPE_TABS` 常數，對應 BQ `doc_type`） |
| 第二列：公司篩選 | `全部公司｜台積電 2330｜…` | 動態（依實際有資料的 ticker） |

- BQ `doc_type` 顯示對照：`major_news` → 重大訊息、`transcript` → 法說會逐字稿、`earnings_call` → 法說會（`news` 不顯示）
- tab count badge 不顯示（同 history 風格）

#### 文件列表（table 格式）

使用 `.ptable`（含 `.ptable-wrap` 橫向捲動），欄位對應 BQ `colpali_pages × company_dim`：

| 欄 | BQ 來源 | 備註 |
|---|---|---|
| 文件 | `source_file` + `fetched_at` | 入庫日顯示於標題下方，16px font-mono |
| 代號 | `ticker` | font-mono |
| 公司 | `company_name`（JOIN `company_dim`） | — |
| 期間 | `fiscal_period` | font-mono，如 `2025Q4` |
| 類型 | `doc_type` | 以 `TYPE_LABELS` 轉中文，顯示為 `.tag.muted` |
| 頁數 | `page_count` | font-mono |
| 狀態 | `ingested` | `true` → `.tag.ok`（已建索引）、`false` → `.tag.muted`（待處理） |
| 發布日 | `published_at` | font-mono，16px muted |

#### 型別定義（`DocRaw` / `DocVM`）

- `DocRaw`：新增 BQ 欄位（`ticker`、`company_name`、`doc_type`、`fiscal_period`、`source_file`、`page_count`、`published_at`、`fetched_at`），舊欄位標為 optional 向下相容
- `DocVM`：清理為純 BQ 欄位，移除 `title`、`kind`、`company`、`period` 等舊欄
- `normalizeDoc`：雙軌 fallback（`raw.ticker ?? raw.company ?? ""`），R4 接通 BQ API 後可移除 optional 舊欄位

### 手機底部導覽「更多」Drawer（`.mob-more-sheet`）

在 `≤ 1230px` 使用 CSS slide-up drawer 取代 Radix `sheet.tsx`（後者依賴 Tailwind，與 AppShell 技術棧不符）。

**z-index 層次**（關鍵：sheet 必須低於 mobnav，避免蓋住底部按鈕）：

| 層 | z-index | 說明 |
|---|---|---|
| `.mobnav` | 40 | 永遠浮在最上層 |
| `.mob-more-sheet` | 38 | open 時從 `bottom: 0` 向上滑入，mobnav 蓋在其上 |
| `.mob-more-overlay` | 37 | 半透明遮罩（`bottom: 60px`，不蓋住 mobnav） |

**關閉方式**：點遮罩、點 sheet 內 Link、路由切換（`useEffect` 監聽 `pathname`）。

**Drawer 內 item 排列**：`.mob-more-grid { display: flex; justify-content: space-around }` — 橫排 flex，外觀與 mobnav 一致，形成「第二列」的視覺延伸。

**CSS 只在 `@media (max-width: 1230px)` 生效**；全域宣告 `display: none` 確保桌機不渲染。

### `.btn.danger`

破壞性操作（刪除確認）用紅色按鈕變體：

```css
.btn.danger { background: rgb(var(--danger)); color: #fff; border-color: rgb(var(--danger)); }
.btn.danger:hover { background: rgb(var(--danger) / .85); }
```

使用原則：僅用於不可逆操作的「最終確認」按鈕，必須搭配取消選項。

### 確認對話卡片（`.hist-confirm-card`）

刪除等破壞性操作的二次確認 UI，複用 `.alert-modal-overlay` 全屏遮罩：

```
alert-modal-overlay（全屏半透明遮罩，點擊關閉）
  └─ hist-confirm-card（居中小卡，animation: alert-enter 滑入）
       ├─ hist-confirm-title（18px / 700）
       ├─ hist-confirm-desc（14px muted，說明不可逆後果）
       └─ hist-confirm-actions（flex row，取消 + 確認刪除）
```

寬度：`min(360px, 90vw)`。目前套用於對話紀錄頁刪除流程，可複用於其他破壞性操作。

### `.chart-empty` 使用規範
- 空態容器一律套用 `.chart-empty`
- 垂直 padding 可用 inline `style={{ padding: "Xpx 16px" }}` 覆蓋，**水平 padding 不得低於 16px**
- 文字固定 `font-size: 16px`，不另設 inline font-size

---

## Utilities

### `.sr-only`

純 CSS 無障礙隱藏——視覺不可見，螢幕閱讀器仍可讀取：

```css
.sr-only {
  position: absolute; width: 1px; height: 1px;
  padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}
```

**使用情境**：新聞列表的 tag 標籤（用於 JS 篩選邏輯，不需視覺呈現）。

### `.page.narrow`

```css
.page.narrow { max-width: 800px; }
```

套用於新聞、對話紀錄、通知三個列表頁面，限制內容寬度，防止在大螢幕上過寬影響閱讀。

---

## 動畫規範

詳見 [`animations.md`](./animations.md)。

**核心原則**：
- CSS keyframe / transition 優先（GPU compositing，不觸發 layout）
- framer-motion 少量使用，僅套用高視覺影響元件（SpotlightCard、TextGenerate）
- 持續動畫（ambient）限用於裝飾性元素，不阻擋操作
- JS 動畫（Number Ticker、rAF）在完成後停止，無持續開銷

**已安裝的動畫相關依賴**：

| 套件 | 版本 | 用途 |
|---|---|---|
| `framer-motion` | latest | SpotlightCard、TextGenerate |
| `tailwind-merge` | ^3.6.0 | `cn()` utility（SpotlightCard className 合併） |
| `clsx` | ^2.1.1 | `cn()` utility |
