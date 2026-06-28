# Peer KPI Grid — 資料來源與格式問題分析

> 本文件說明 `peer/page.tsx` 中兩個 KPI Grid 元件的資料來源、格式化路徑，
> 以及目前「值太長」的根本原因與改善方向。
> 最後更新：2026-06-25

---

## 一、兩種 KPI Grid 的觸發條件

| 元件                    | 觸發條件                                           | 資料來源端點           |
| ----------------------- | -------------------------------------------------- | ---------------------- |
| `PeerKpiGridLive`     | `/peer-compare` API 成功回傳 `peerResult`      | `POST /peer-compare` |
| `PeerKpiGridFallback` | `peerResult` 為 null（查詢中 / 失敗 / 尚未查詢） | `GET /financials`    |

---

## 二、`PeerKpiGridLive`（主要路徑）

### 2-1. 資料流

```
前端 api.peerCompare()
  → POST /peer-compare  (src/polaris/api.py)
    → StructuredStore.list_financials(ticker=A, period=P)
    → StructuredStore.list_financials(ticker=B, period=P)
      → BQ: SELECT ... FROM polaris_core.v_financial_metrics_semantic
            WHERE ticker = @ticker AND fiscal_period = @period
  → 組 kpis[]  →  normalizePeerCompare()  →  peerResult.kpis
    → PeerKpiGridLive 顯示 kpi.a.v / kpi.b.v
```

### 2-2. BQ 來源

| BQ View | `polaris_core.v_financial_metrics_semantic`                                    |
| ------- | -------------------------------------------------------------------------------- |
| 底層表  | `financial_metrics`（4,620 列）                                                |
| 使用欄  | `ticker`, `fiscal_period`, `metric_id`, `value`, `unit`, `source_id` |

### 2-3. 顯示的指標（依優先序，有資料才顯示）

| 優先序 | `metric_id`    | 顯示標籤   | BQ`unit` 值              |
| ------ | ---------------- | ---------- | -------------------------- |
| 5      | `eps`          | EPS        | `新台幣元/股`            |
| 4      | `gross_margin` | 毛利率     | `%`                      |
| 3      | `net_margin`   | 淨利率     | `%`                      |
| 2      | `revenue_yoy`  | 月營收 YoY | `%`                      |
| 1      | `revenue`      | 月營收     | `新台幣千元` 或 `千元` |


### 2-4. 後端格式化函數（`api.py` `_fmt_value`）

```python
def _fmt_value(value: float, unit: str | None) -> str:
    unit = unit or ""
    display_unit = unit.replace("新台幣", "").strip()
    if unit == "%":
        return f"{value:.2f}%"          # 固定 2 位小數
    if "千元" in unit:
        yi = value / 100_000            # 千元 → 億（1 億 = 100,000 千元）
        return f"{yi:,.0f} 億" if yi >= 100 else f"{yi:,.1f} 億"
    return f"{value:g} {display_unit}".strip() if display_unit else f"{value:g}"
```

### 2-5. 目前值太長的問題點

| 欄位              | 問題                                                             | 範例                             |
| ----------------- | ---------------------------------------------------------------- | -------------------------------- |
| EPS               | `{value:g}` 保留最多 6 位有效數字，單位後綴 `元/股` 增加長度 | `12.54 元/股`                  |
| 月營收 ≥ 100億   | `{yi:,.0f}` 加千位逗號                                         | `2,500 億`（台積電等大型公司） |
| 差異值（diff）    | 同樣走`_fmt_value` 差值，格式與值欄一致                        | `+123 億`、`+2.40pp`         |
| gross_margin diff | `{abs(diff):g}pp` 無小數控制                                   | `3.7825pp`（小數未截斷）       |

---

## 三、`PeerKpiGridFallback`（備援路徑）

### 3-1. 資料流

```
useFinancials(aTicker)  →  GET /financials?ticker=A
useFinancials(bTicker)  →  GET /financials?ticker=B
  → BQ: SELECT ticker, fiscal_period, metric_id, value, unit,
               source_id, published_at, year, month
          FROM polaris_core.v_financial_metrics_semantic
          WHERE ticker = @ticker
          ORDER BY published_at DESC
          LIMIT 200
→ getMetricForPeriod(rows, metricId, period, month?)
→ fmtRevenue() / fmtYoy()
→ PeerKpiGridFallback 顯示
```

### 3-2. 顯示的指標（固定只有兩個）

| 指標       | `metric_id`   | 前端格式化函數                                       | 格式範例    |
| ---------- | --------------- | ---------------------------------------------------- | ----------- |
| 月營收     | `revenue`     | `fmtRevenue()` → `value / 100_000` → `X.X億` | `125.3億` |
| 月營收 YoY | `revenue_yoy` | `fmtYoy()` → `+X.X%`                            | `+15.3%`  |

### 3-3. 月份過濾邏輯

```typescript
// selectedMonth 由年/季/月 selector 決定
getMetricForPeriod(rows, metricId, fiscalPeriod, selectedMonth)
// 有 selectedMonth → 精確找 r.month === selectedMonth
// 無 selectedMonth（全季）→ 回傳 fiscal_period 下第一筆（最新 published_at）
```

⚠️ 同一 `(ticker, fiscal_period, metric_id)` 在 BQ 可能有多列（Q1 = 1月、2月、3月各一列），
`ORDER BY published_at DESC LIMIT 200` 取後，`rows.find()` 只取第一筆。
若要特定月份，必須傳入 `selectedMonth`。

---

## 四、改善建議（解決「值太長」）

### 4-1. 後端 `_fmt_value` 修正（`api.py`）

| 情況             | 目前                                   | 建議改為                                       |
| ---------------- | -------------------------------------- | ---------------------------------------------- |
| EPS（`元/股`） | `{value:g} 元/股` → `12.54 元/股` | `{value:.2f}` → `12.54`（單位移到 label） |
| pp 差異          | `{abs(diff):g}pp`                    | `{abs(diff):.2f}pp` → 固定 2 位             |
| 大額億數         | `{yi:,.0f}` 含逗號 → `2,500 億`   | `{yi:.0f}` 不加逗號 → `2500 億`           |

### 4-2. 前端 KPI 卡片顯示

`pk-val` 目前直接顯示後端回傳的 `kpi.a.v`（含單位字串）。
建議在前端 `normalizePeerCompare()` 拆分值與單位：

```typescript
// 目前
a: { v: "12.54 元/股", citations: [...] }

// 建議
a: { v: "12.54", unit: "元/股", citations: [...] }
```

然後在卡片 UI 上：

- `pk-val` 只顯示數字
- `pk-label` 或 `pk-unit`（新增）顯示單位，字體縮小

### 4-3. 差異值（diff）截斷

目前 `_metric_diff()` 對百分比用 `{abs(difference):g}pp`，
浮點數如 `3.7825` → `3.7825pp`。
改為 `{abs(difference):.2f}pp` 即可固定 2 位小數。

---

## 五、引用來源對照

| KPI              | 引用`source_id` 來自                                              | 前端顯示位置       |
| ---------------- | ------------------------------------------------------------------- | ------------------ |
| Live grid 各 KPI | `kpi.a.citations[0].src`（即 BQ `financial_metrics.source_id`） | 側欄「引用追蹤器」 |
| Fallback grid    | `useFinancials` rows 的 `source_id`（未串入引用追蹤器）         | ⚠️ 目前未顯示    |

---

## 六、快速查詢（確認 BQ 資料）

```sql
-- 確認某公司在某期別有哪些指標
SELECT metric_id, value, unit, source_id, month
FROM `polaris-desk-team.polaris_core.v_financial_metrics_semantic`
WHERE ticker = '2330' AND fiscal_period = '2026Q2'
ORDER BY metric_id, month;
```
