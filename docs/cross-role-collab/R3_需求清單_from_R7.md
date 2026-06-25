# R3 需求清單（R7 前端提出）

> 整理日期：2026-06-17｜最後更新：2026-06-25 晚｜撰寫：R7

---

## ⚠️ R3 仍待交付清單（截至 2026-06-24）

| 端點 | 影響功能 | 備註 |
|------|---------|------|
| `GET /alerts` 補 `origin`/`title`/`source`/`time` 欄位 | 研究助理 + 同業比較監控警示面板空白 | 欄位規格見 §1 |
| `GET /tracking-feed` | 通知中心「追蹤通知」tab 空白 | 規格見 §8 |
| `GET /suggestions?mode=peer` | 同業比較快速提問 chip 仍為靜態 hardcode | 規格見 §5 |
| `POST /research` 補 `chart` + `kpis` | 量化分析 KPI 卡 + 毛利率趨勢圖（前端已隱藏等後端） | ⏰ 時間充裕才做；規格見 §9 |
| `POST /contradiction` 請求格式更新 | 改接受 `citations[]`（新格式）取代舊 `kpis+summary` | 2026-06-25 新增；規格見 §2b |
| `POST /resolve` 語意強化 | `inferTickerFromQuery` 前端版無法處理語意查詢，需後端語意識別 | 2026-06-25 新增；規格見 §10 |

> Demo 預計 2026-06-25；R2 已確認 Demo 可用 mock 撐場，上述端點為 Demo 後正式版本需求。


> ⚠️ **2026-06-24 更新**：GitHub Issue #3 已關閉，改追蹤 **[Issue #23](https://github.com/holajennytw/polaris-desk/issues/23)**。
> Issue #23 整合了 R3 + R4 的全資料來源 RAG 需求，含完整 `POST /research`、`GET /chunk/{source_id}`、`POST /peer-compare` response schema。
> 優先順序：`POST /research` 跨 doc_type → `GET /chunk/{source_id}` → `POST /peer-compare` → 其餘端點。
>
> 本文件保留為詳細 API 規格參考，以下各節規格仍有效。

---

## 優先級總覽（2026-06-24 傍晚更新）

| # | 端點 | 優先 | 狀態 | 對應前端功能 |
|---|------|------|------|------------|
| 1 | `GET /alerts` 補欄位 | 🔴 高 | ⏳ 仍未交付 | 研究助理 + 同業比較 監控警示面板 |
| 2 | `POST /contradiction` | 🔴 高 | ✅ **PR #25 已 merge** | 研究助理 + 同業比較 矛盾偵測 |
| 3 | `POST /research` citation metadata | 🟡 中 | ✅ **PR #25 已 merge**（三路檢索 + doc_type split） | 兩頁引用追蹤器文件標籤 |
| 4 | `GET /chunk/{source_id}` | 🔴 高 | ✅ **PR #25 已 merge** | 引用追蹤器點擊展開原文 |
| 5 | `GET /suggestions`（同業比較版） | 🟡 中 | ⏳ 仍未交付 | 同業比較頁快速提問 chip |
| 6 | `POST /peer-compare` | ⚪ 排工時 | ✅ **PR #25 + PR #27 已 merge**（前後端全串接完成 2026-06-25） | 同業比較整頁 |
| 7 | `POST /history` / `GET /history` | 🟡 中 | ✅ **R7 自行實作**（Firestore，PR #11） | 對話紀錄 |
| 8 | `GET/POST /subscriptions` | 🟡 中 | ✅ **R7 自行實作**（Firestore，PR #11） | 通知中心訂閱設定 |
| 8b | `GET /tracking-feed` | 🟡 中 | ⏳ 仍未交付 | 追蹤通知顯示 |
| 9 | `POST /research` 補 `chart` + `kpis` | 🟡 中 | ⏳ 仍未交付（前端量化分析已隱藏） | 研究助理頁「量化分析」圖表 + KPI 卡 |
| 10 | `POST /contradiction` 請求格式更新 | 🟡 中 | ⏳ 新增需求（2026-06-25） | 移除前端 `buildMockContradictions()` mock |
| 11 | `POST /resolve` 語意強化 | 🟢 低 | ⏳ 新增需求（2026-06-25） | 移除前端 `inferTickerFromQuery()` 本地比對 |

---

## 1. `GET /alerts` — 補齊欄位（兩個頁面都需要）

### 對應功能

- **研究助理頁** → 右側「監控系統警示」面板，過濾 `origin === "research"`
- **同業比較頁** → 右側「監控系統警示」面板，過濾 `origin === "peer"`

### 問題

目前後端 `AlertResponse` 缺少以下欄位，導致兩個頁面的監控面板完全空白：
- `origin`（必填，決定警示出現在哪一頁）
- `title`（前端顯示警示標題）
- `source`（來源描述）
- `time`（時間字串）
- `stock_id`（股票代碼，現在後端叫 `ticker`）

### 期望 Response（陣列）

```json
[
  {
    "event_id": "evt-001",
    "origin": "research",
    "severity": "alert",
    "title": "台積電法說數字與財報出入",
    "summary": "法說會提及 Q2 營收成長 25%，但財報顯示同期衰退 3%，來源矛盾。",
    "source": "MOPS · 2330",
    "time": "10:30",
    "stock_id": "2330"
  },
  {
    "event_id": "evt-002",
    "origin": "peer",
    "severity": "watch",
    "title": "聯發科 vs 聯詠毛利率異常落差",
    "summary": "同期比較發現毛利率差異超過正常產業範圍，建議核查數據來源。",
    "source": "同業比較引擎 · 2454 vs 3034",
    "time": "11:15",
    "stock_id": "2454"
  }
]
```

### 欄位規格

| 欄位 | 型別 | 說明 |
|------|------|------|
| `event_id` | string | 唯一 ID |
| `origin` | `"research"` \| `"peer"` | **必填**，前端用此欄位路由至正確頁面 |
| `severity` | `"alert"` \| `"watch"` \| `"info"` | alert=紅、watch=橘、info=灰 |
| `title` | string | 一行標題 |
| `summary` | string | 詳細說明 |
| `source` | string | 來源描述 |
| `time` | string | 時間（`"HH:mm"` 或 ISO 字串） |
| `stock_id` | string | 股票代碼 |

---

## 2. `POST /contradiction` — 矛盾偵測（兩個頁面都需要）

### 對應功能

- **研究助理頁** → 右側「監控系統警示」面板，`origin === "contradiction"` 的項目
- **同業比較頁** → 右側「監控系統警示」面板，`origin === "contradiction"` 的項目

### 觸發時機（兩頁共同邏輯）

1. 查詢完成後**自動觸發**一次
2. 使用者手動點「矛盾偵測」按鈕

### 目前狀態

端點不存在 → 前端 fallback 到 client-side 規則式 mock（比對 KPI 值與摘要文字）。

### Request

```json
{
  "kpis": [
    {
      "label": "全年美元營收指引",
      "value": "中段 25%",
      "unit": "",
      "delta": null,
      "trend": null
    }
  ],
  "summary": [
    {
      "text": "Q2 營收成長將達 25% 以上，CoWoS 需求持續強勁。",
      "cite": "stub-2330-2026Q1-call",
      "page": "p.7"
    }
  ]
}
```

### 期望 Response

```json
{
  "alerts": [
    {
      "id": "contra-001",
      "origin": "contradiction",
      "level": "mid",
      "title": "全年指引：KPI 與摘要數字表述不一致",
      "summary": "KPI 卡顯示「中段 25%」，摘要引述「25% 以上」，同份法說來源表述有落差，建議核對原文 p.7。",
      "source": "矛盾偵測 · stub-2330-2026Q1-call vs KPI",
      "time": "14:22"
    }
  ]
}
```

### 欄位規格

| 欄位 | 型別 | 說明 |
|------|------|------|
| `alerts` | array | 矛盾清單；無矛盾時回 `[]`，前端會顯示「交叉比對通過」 |
| `alerts[].id` | string | 唯一 ID |
| `alerts[].origin` | `"contradiction"` | 固定值 |
| `alerts[].level` | `"high"` \| `"mid"` \| `"info"` | 風險等級（前端 modal 顯示高/中/低） |
| `alerts[].title` | string | 一行標題 |
| `alerts[].summary` | string | 說明 + 建議提示 |
| `alerts[].source` | string | 涉及的引用來源 |
| `alerts[].time` | string | 偵測時間 |

### 備註

偵測到高/中風險時，請問是否會自動 push 到 NotificationService？還是需要 R7 前端拿到結果後另外呼叫 `POST /notifications/events`？

---

## 2b. `POST /contradiction` — 請求格式更新（2026-06-25 新增）

> 此節為 §2 的格式升版需求。PR #25 已實作舊格式（`kpis + summary`），
> 但 2026-06-25 R7 前端改以 `citations[]` 為中心（新增 `CitationOrigin` 型別），
> 建議 R3 評估是否更新端點格式。若維持舊格式，前端需在呼叫前自行組裝 kpis/summary。

### 背景

舊的請求格式依賴前端把 KPI 和摘要拼好再送；新格式直接把 retriever 回傳的 citations 送過去，讓後端自行判斷矛盾。後者不需要前端做格式轉換，耦合較低。

### 新格式 Request

```json
{
  "citations": [
    {
      "source_id": "2330-2025Q4-revenue-chunk-01",
      "snippet": "本季營收 8,028 億元，較去年同期成長 39%",
      "origin": "embedding"
    },
    {
      "source_id": "2330-2025Q4-revenue-chunk-03",
      "snippet": "2025Q4 合併營收約 7,985 億元",
      "origin": "bm25"
    }
  ]
}
```

`origin` 可能值：`"stub" | "bm25" | "embedding" | "colpali" | "rerank" | "news"`（對應 `CitationOrigin`，前端 `types/api.ts#L86`）

### 新格式 Response

```json
{
  "pairs": [
    {
      "a_source_id": "2330-2025Q4-revenue-chunk-01",
      "b_source_id": "2330-2025Q4-revenue-chunk-03",
      "description": "兩份文件對 2025Q4 營收數字說法不一致（8,028 億 vs 7,985 億）",
      "severity": "high"
    }
  ]
}
```

若無矛盾，回傳 `{ "pairs": [] }`。

### R7 前端後續動作（R3 更新格式後）

- 刪除 `research/page.tsx` 裡的 `buildMockContradictions()` 函式（約 30 行）
- `runContradictionCheck` 改為純 API 呼叫，失敗時顯示「矛盾偵測暫時無法使用」

---

## 3. `POST /research` — Citation metadata（PR #6 確認）

### 對應功能

**研究助理 + 同業比較頁** → 引用追蹤器文件類型標籤、日期、財報季別

### 狀態

PR #6 修在 retriever 端，api.py 現有寫法不用改。PR merge 後 R7 將測試以下欄位是否正確帶入：

```json
{
  "source_id": "chunk-2330-2026Q1-abc",
  "snippet": "CoWoS 先進封裝...",
  "origin": "embedding",
  "doc_type": "transcript",
  "published_at": "2026-04-18",
  "fiscal_period": "2026Q1"
}
```

`doc_type` 對應前端標籤：`transcript`→法說逐字稿、`major_news`→重大訊息、`news`→新聞

> ⚠️ `presentation`（法說簡報）與 `fin`（合併財報）目前 BQ `chunks` 表**無此值**（欄位表 §1 實際值只有以上三種），待 R4 補充入庫後再加回前端 mapping。

---

## 4. `GET /chunk/{source_id}` — 引用原文（新端點）

### 對應功能

**研究助理 + 同業比較頁** → 引用追蹤器點擊展開卡片時，顯示 BQ 裡的實際文件片段與頁碼

### 目前狀態

前端 DocViewer **已可開啟**（降級模式）：將 Citation 的 `snippet` 欄位切成句子顯示在 pdf-mock 區塊，引用片段也正常呈現。但有以下限制：

| | 現在（snippet 降級） | 交付 `GET /chunk/{source_id}` 後 |
|--|------|------|
| 內文 | snippet 切句（通常 1–3 行） | 完整段落原文 |
| 頁碼 | 來自 `published_at` 或 snippet | 真實頁碼 |
| 可信度標籤 | hardcoded `"mid"` | 後端計算的 trust score |

`GET /chunk/{source_id}` 交付後，前端不需要改結構，只需在 `handleOpenDoc` 裡改為呼叫此端點取 `content`，替換現有的 `body` 組裝邏輯。

### 期望 Response

```json
{
  "source_id": "chunk-2330-2026Q1-abc",
  "title": "台積電_2026Q1_法說會逐字稿.pdf",
  "doc_type": "transcript",
  "ticker": "2330",
  "fiscal_period": "2026Q1",
  "published_at": "2026-04-18",
  "page": "p.3",
  "content": "完整的段落文字內容..."
}
```

---

## 5. `GET /suggestions` — 同業比較版快速提問 chip

### 對應功能

**同業比較頁** → searchbar 上方的快速提問 chip（目前是靜態 hardcoded PRESETS）

### 目前狀態

研究助理頁已串接 `/suggestions`（回傳 BQ 內有資料的公司最新法說 + LLM 生成問題）。同業比較頁的 chip 仍為靜態：
```
比較台積電與聯發科毛利率 / 台積電 vs 鴻海 法說會重點 / 聯發科與聯詠估值比較
```

### 討論方向（待開會確認）

`mode` 參數由後端加，前端直接渲染回傳結果，不做字串轉換。

背景：若前端在 chip 上自行加前綴，未來後端調整措辭時前端需同步修改，造成耦合；由後端統一管理 prompt 措辭較易維護。

### Request

```
GET /suggestions?mode=research   ← 現有，不變
GET /suggestions?mode=peer       ← 新增，用比較情境 prompt 生成問句
```

### 期望 Response（mode=peer）

```json
["比較台積電與聯發科毛利率", "台積電 vs 鴻海 法說重點對比", "聯發科與聯詠估值差異分析"]
```

### R7 前端對應動作

同業比較頁將 hardcoded PRESETS 替換為 `useSuggestions({ mode: "peer" })` hook，渲染邏輯與研究助理頁完全相同。

---

## 6. `POST /peer-compare` — 同業比較（排工時）

> ⚠️ **2026-06-24 更新**：Response 格式已由 R7 在 `frontend/src/types/api.ts` 正式定義（`PeerCompareResponse`）。
> 以下規格以 TypeScript 介面為準；Issue #23 comment 也附有此介面供參考。

### 對應功能

**同業比較頁** — 目前整頁為 hardcoded mock 資料，等 R3 排入工時後替換。

### 衍生指標計算（待確認分工）

`financial_metrics` 表只有原始值，沒有毛利率等比率。計算方式：

- `gross_margin (%)` = `gross_profit` / `revenue` × 100
- `operating_margin (%)` = `operating_income` / `revenue` × 100
- `revenue_yoy (%)` = 直接取 `metric_id='revenue_yoy'`（BQ 已有）

衍生指標由哪一層計算（workflow 內 / 前端），**待確認**。

### Request

```json
{
  "a_ticker": "2330",
  "b_ticker": "2454",
  "fiscal_period": "2026Q1",
  "question": "比較毛利率與法說重點"
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `a_ticker` | string | 公司 A 股票代號 |
| `b_ticker` | string | 公司 B 股票代號 |
| `fiscal_period` | string | 選填，預設取兩家共同最新期（格式 `YYYYQn`）|
| `question` | string | 選填，使用者輸入的自然語言問題 |

### Response TypeScript 型別（以此為準）

```typescript
// frontend/src/types/api.ts

interface PeerCompareTrendPoint {
  period:   string;        // "2025Q1"
  metric:   string;        // "gross_margin" | "op_margin" | "revenue_yoy"
  a_value:  number | null;
  b_value:  number | null;
}

interface PeerCompareResponse {
  a_ticker:         string;
  b_ticker:         string;
  fiscal_period:    string;
  kpis:             PeerKpiRaw[];           // { label, a: GroundedValue, b: GroundedValue, diff, better }
  financial:        PnlRowRaw[];            // { metric, a: GroundedValue, b: GroundedValue, note }
  calls:            CallRowRaw[];           // { dim, topic, a: {stance, tone, quote, cite}, b: {...} }
  valuation:        ValuationRowRaw[];      // { metric, a: string, b: string, note }
  trend:            PeerCompareTrendPoint[];
  summary:          string;
  compliance_status: string;               // "passed" | "blocked" | "unknown"
}
```

### 各欄位來源

| 欄位 | 來源 | 說明 |
|------|------|------|
| `kpis[]` | `financial_metrics` 計算 | 毛利率、營業利益率、營收 YoY；`diff`/`better` 後端算好 |
| `financial[]` | `financial_metrics` | 損益指標對比表；`a`/`b` 可為 `GroundedValue`（附 citation）|
| `calls[]` | LLM + `chunks` transcript | 法說主題矩陣；`tone` 為 `"pos"/"neu"/"neg"` |
| `valuation[]` | `financial_metrics` (eps) + 待補股價 | PE/PB 目前 BQ 無股價，填 `"—"` |
| `trend[]` | `financial_metrics` 多期 | 每筆一個 `{period, metric, a_value, b_value}` |
| `summary` | LLM | 比較摘要（單一字串，前端分行顯示）|
| `compliance_status` | R3 合規檢查 | `"passed"` / `"blocked"` / `"unknown"` |

### 備註

- `fiscal_period` 未帶入時，後端取兩家公司共同的最新期
- PE / PB / EV/EBITDA 目前 BQ 無股價資料，暫填 `"—"`，`note` 欄說明原因
- `calls[].a.cite` / `calls[].b.cite` 填 `source_id`，前端引用追蹤器會呼叫 `GET /chunk/{source_id}`

---

## 7. `POST /history` — 對話紀錄寫入

> ⚠️ **前置條件：需等 R2 決定儲存架構後再實作。**
> 目前前端已改用 `localStorage` 暫存（MVP），R2 決定用 BQ / Firestore 後，R3 再實作此端點，前端再切換。
> 詳見 `docs/cross-role-collab/R2_需求清單_from_R7.md` §2。

### 對應功能

**對話紀錄頁（/history）** — 使用者在研究助理或同業比較頁送出查詢後，前端自動呼叫此端點寫入一筆紀錄，讓 /history 頁能顯示歷史查詢。

### 觸發時機

- 研究助理頁 `POST /research` 收到回應後，前端立即呼叫 `POST /history`
- 同業比較頁 `POST /peer-compare` 收到回應後，前端立即呼叫 `POST /history`

### Request

```json
{
  "origin": "research",
  "query": "台積電 2026Q1 法說會營運重點",
  "tickers": ["2330"],
  "timestamp": "2026-06-17T10:30:00Z"
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `origin` | `"research"` \| `"peer"` | 來源頁面 |
| `query` | string | 使用者輸入的查詢文字 |
| `tickers` | string[] | 涉及的股票代碼（可多個） |
| `timestamp` | string | ISO 8601 時間字串 |

### 期望 Response

```json
{
  "record_id": "hist-20260617-001",
  "status": "ok"
}
```

### `GET /history` — 對話紀錄讀取

> 與 `POST /history` 為同一組端點，規格一併列出。

**期望 Response**

```json
[
  {
    "id": "hist-20260617-001",
    "query": "台積電 2026Q1 法說會營運重點",
    "page": "research",
    "time": "2026-06-17T10:30:00Z",
    "tags": ["2330"]
  }
]
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | string | 紀錄唯一 ID |
| `query` | string | 使用者查詢文字 |
| `page` | `"research"` \| `"peer"` | 來源頁面（前端用此欄位決定跳轉目標） |
| `time` | string | ISO 8601 時間字串 |
| `tags` | string[] | 涉及的 tickers，前端顯示為標籤 |

> ⚠️ 此規格來自 `R2_需求清單_from_R7.md §2`；`GET /history` 的實作責任（R2 或 R3）待開會確認（見開會議程 B）。

### 備註

- 若後端 workflow 執行時能自動記錄（不需前端另外呼叫），請告知，前端可省略 `POST /history` 呼叫
- /history 頁的「點擊跳轉」功能（帶 query 回對應頁面）前端已完成，只缺寫入端

---

## 8. 訂閱相關端點（`GET /subscriptions`、`POST /subscriptions`、`GET /tracking-feed`）

### 對應功能

**通知中心（/notifications）→「訂閱設定」tab** — 使用者主動選擇要追蹤的公司後，呼叫此端點儲存訂閱清單；另需 `GET /subscriptions` 讓前端初始載入已訂閱的公司。

### 端點清單

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/subscriptions` | 取得目前使用者的訂閱清單 |
| `POST` | `/subscriptions` | 儲存（覆蓋）訂閱清單 |
| `GET` | `/tracking-feed` | 依訂閱 tickers 回傳最新事件清單（後端批次查詢 + 排序） |

### POST Request

```json
{
  "tickers": ["2330", "2454", "2317"]
}
```

### GET Response

```json
{
  "tickers": ["2330", "2454", "2317"]
}
```

### POST Response

```json
{
  "status": "ok",
  "tickers": ["2330", "2454", "2317"]
}
```

### 前端使用邏輯

1. 頁面載入：`GET /subscriptions` 取得清單 → 顯示已勾選的公司
2. 使用者更改選項 → 點「儲存」→ `POST /subscriptions` 送出完整新清單
3. 「追蹤通知」tab 載入：`GET /tracking-feed?tickers=2330,2454` → 顯示最新事件列表

### `GET /tracking-feed` 規格

**Request（query params）**

| 參數 | 型別 | 說明 |
|------|------|------|
| `tickers` | string | 逗號分隔的股票代號，如 `2330,2454,2317` |
| `limit` | number | 筆數上限，預設 20 |

**期望 Response**

```json
{
  "items": [
    {
      "event_id": "evt-2330-001",
      "ticker": "2330",
      "company_name": "台積電",
      "event_key": "earnings_call",
      "title": "台積電 2026Q1 法說會",
      "published_at": "2026-04-18",
      "source_url": "https://..."
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `event_id` | string | 唯一 ID |
| `ticker` | string | 股票代號 |
| `company_name` | string | 中文公司名（JOIN `company_dim`） |
| `event_key` | string | `major_news` / `monthly_revenue` / `earnings_call` / `news`（R6 更名，原 `event_type`）|
| `title` | string | 事件標題 |
| `published_at` | string | 發布日期 |
| `source_url` | string | 原始連結（可為 null） |

---

## 9. `POST /research` — 補 `chart` + `kpis` 欄位（量化分析）

### 對應功能

**研究助理頁** → 「量化分析」panel 的長條圖 + KPI 卡（目前永遠顯示「財務指標資料建置中」）

### 現況

`normalizeResearch()` 目前硬設 `chart: []`、`kpis: []`，不管後端回傳什麼都不顯示。
需要 R3 在 `POST /research` workflow 最後，依偵測到的 ticker 查 `financial_metrics` 表，附在 response 裡（方案 A：單次 API call，不增加前端 round-trip）。

### 期望 Response（新增欄位，附加在現有 response 後）

```json
{
  "final_answer": "...",
  "react_steps": [...],
  "evidence": [...],
  "chart": [
    { "label": "2025Q2", "value": 53.1 },
    { "label": "2025Q3", "value": 54.8 },
    { "label": "2025Q4", "value": 56.2 },
    { "label": "2026Q1", "value": 57.8 }
  ],
  "kpis": [
    {
      "label": "毛利率",
      "value": "57.8",
      "unit": "%",
      "delta": "QoQ +1.6pp",
      "trend": "up",
      "cite_key": "chunk-2330-2026Q1-fin"
    },
    {
      "label": "營業利益率",
      "value": "47.5",
      "unit": "%",
      "delta": "QoQ +0.8pp",
      "trend": "up",
      "cite_key": "chunk-2330-2026Q1-fin"
    }
  ]
}
```

### 欄位規格

**`chart[]`**

| 欄位 | 型別 | 說明 |
|------|------|------|
| `label` | string | 季別，如 `"2026Q1"` |
| `value` | number | 毛利率百分比（不含 `%`），如 `57.8` |

建議回傳近 4–6 季，由 `financial_metrics` 以 `gross_profit / revenue × 100` 計算（BQ 無 `gross_margin` metric_id，只有 `gross_profit` 與 `revenue`，需 R3 在 workflow 內自行計算後再填入），依 `fiscal_period` 排序。

**`kpis[]`**

| 欄位 | 型別 | 說明 |
|------|------|------|
| `label` | string | 指標名稱 |
| `value` | string | 數值（字串） |
| `unit` | string | 單位，如 `"%"`、`"億元"` |
| `delta` | string | 與前期差異，如 `"QoQ +1.6pp"` |
| `trend` | `"up"` \| `"down"` \| `"flat"` | 趨勢方向 |
| `cite_key` | string | 來源 source_id（引用接地） |

### R7 配合動作（R3 交付後）

`adapters.ts` 的 `normalizeResearch()` 解封兩行：

```typescript
// 改前
return { query, kpis: [], summary, chart: [], react, citations };

// 改後
return { query, kpis: (raw.kpis ?? []).map(normalizeKpi), summary, chart: raw.chart ?? [], react, citations };
```

不需改 Chart component 或 KpiCard，前端結構已就緒。

---

## 10. `POST /resolve` — 語意 ticker 識別強化（2026-06-25 新增）

### 背景

`POST /resolve` 端點已存在，前端 `api.resolve(query)` 也已接通。但 `hooks/useFinancials.ts` 目前沒有使用它，而是用本地函式 `inferTickerFromQuery()` 做字串比對：

```typescript
// 現在（前端版）—— 只比對 id 和 name，語意查詢無效
function inferTickerFromQuery(query, companies) {
  return companies.find(c =>
    query.includes(c.id) || query.includes(c.name)
  )?.id ?? null;
}
```

「台積電 2025Q4 營收」可以找到 `2330`，但「半導體龍頭上季獲利」找不到。

### 前端需要的改善

1. **語意識別**：「半導體龍頭」應能解析成 `2330`
2. **複數 ticker**：「台積電和聯發科比較」應回傳 `["2330", "2454"]`（`ordered` 陣列已支援）
3. **無結果處理**：真的找不到時回傳 `ordered: []`，前端顯示「找不到相關公司」

### 現有 Response 格式（不需改）

```typescript
// frontend/src/types/api.ts
interface ResolveResponse {
  ordered: Array<{ id: string; name: string; status: "ok" | "nodata" }>;
  period: string;
  tab: string;
}
```

### 優先度

**低**：字串比對已能處理大多數直接輸入公司名稱 / 代碼的查詢，語意識別是品質提升。

### R7 前端後續動作（R3 改善後）

- `hooks/useFinancials.ts` 的 `inferTickerFromQuery()` 廢棄，改呼叫 `api.resolve(query)`
- 保留一個 Sprint 再刪（其他頁面可能仍在引用）

---

## 附：前端 Alert 資料流說明

```
R3 Watchdog → GET /alerts → 前端過濾 origin
  ├─ origin="research" → 研究助理頁監控面板（即時顯示，不持久化）
  └─ origin="peer"     → 同業比較頁監控面板（即時顯示，不持久化）

POST /contradiction → 前端 contraAlertStore（sessionStorage）
  └─ origin="contradiction" → 兩頁監控面板共用（session 結束即清除）
```
