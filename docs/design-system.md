# Polaris Desk — Design System

> 整理日期：2026-06-18｜維護：R7
> 本文件為前端 CSS 設計規範的單一事實來源。修改 `polaris.css` 時同步更新此文件。

---

## Breakpoints

| 名稱 | 範圍 | 說明 |
|------|------|------|
| `xl` | ≥ 1400px | 大型桌機；sidebar nav 完整顯示 |
| `lg` | 1231–1399px | 中型桌機；sidebar nav 仍可見，字體略縮 |
| `md` | 1181–1230px | 小型桌機 / 大平板；sidebar 隱藏，切換為 mobnav |
| `sm` | 1180px 以下 | 單欄版型，sidebar content 收合 |
| `xs` | ≤ 560px | 小螢幕，KPI grid 調整為單欄 |

---

## Typography

### Sidebar Nav（`.nav-item`）

| Breakpoint | font-size | 說明 |
|------------|-----------|------|
| ≥ 1400px（xl） | **20px** | 桌機標準 |
| 1231–1399px（lg） | **18px** | 中型桌機縮減 |
| ≤ 1230px | — | sidebar 隱藏，改用 mobnav |

**mobnav**（底部導覽列，≤ 1230px）

| 元素 | font-size |
|------|-----------|
| `.mobnav-item` label | 14px |
| `.mobnav-item` icon | 20×20px |

### Nav 分類標籤（`.nav-label`）

| 屬性 | 值 |
|------|----|
| font-size | 14px |
| font-weight | 600 |
| letter-spacing | 0.14em |
| text-transform | uppercase |

### 空態文字（`.chart-empty`）

| 屬性 | 值 |
|------|----|
| font-size | 16px |
| color | `rgb(var(--muted))` |
| padding | 20px 16px（可被 inline style 覆蓋垂直值） |

---

## Spacing

### Panel

| 元素 | 值 |
|------|----|
| `.panel-head` padding | `12px 16px` |
| `.panel-body` padding | `16px` |
| `.compliance` margin | `16px 0` |

### Touch Targets（≤ 1230px，即 `md` 以下）

**規則：所有可互動功能元素，觸控範圍不得小於 44×44px。**

下列元素在 `@media (max-width: 1230px)` 已強制套用：

| 元素 | 規則 |
|------|------|
| `.btn` | `min-height: 44px` |
| `.icon-btn` | `width: 44px; height: 44px` |
| `.mobnav-item` | `min-height: 44px` |
| `.chip` | `min-height: 44px; display: inline-flex; align-items: center` |
| `.news-tab` | `min-height: 44px` |
| `.cpick-btn` | `min-height: 44px` |
| `.cite-item` | `min-height: 44px` |

**新增互動元素清單**：新增任何在 `md` 以下可點擊的元素（tab、chip、picker、list item）時，必須同步在此 media query 加入 `min-height: 44px` 規則。

---

## Component Notes

### `.nav-item` icon 大小
`.nav-item svg` 固定 **20×20px**，與 20px 字體對齊。
Collapsed sidebar（68px rail 寬）：icon 置中於 48px 可用寬度（68px − 左右各 10px nav padding），20×20 排版正常。

### `.chart-empty` 使用規範
- 空態容器一律套用 `.chart-empty`
- 垂直 padding 可用 inline `style={{ padding: "Xpx 16px" }}` 覆蓋，**水平 padding 不得低於 16px**
- 文字固定 `font-size: 16px`，不另設 inline font-size
