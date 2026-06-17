# R3 需求清單（R7 前端提出）

> 整理日期：2026-06-17｜撰寫：R7
> 本文件列出前端所有需要 R3 實作或修正的 API 端點，含完整 request / response 規格。

---

## 優先級總覽

| # | 端點 | 優先 | 狀態 | 對應前端功能 |
|---|------|------|------|------------|
| 1 | `GET /alerts` 補欄位 | 🔴 高 | 欄位不完整 | 研究助理 + 同業比較 監控警示面板 |
| 2 | `POST /contradiction` | 🔴 高 | 端點不存在 | 研究助理 + 同業比較 矛盾偵測 |
| 3 | `POST /research` citation metadata | 🟡 中 | PR #6 待 merge | 兩頁引用追蹤器文件標籤 |
| 4 | `GET /chunk/{source_id}` | 🔴 高 | 端點不存在 | 引用追蹤器點擊展開原文 |
| 5 | `GET /suggestions`（同業比較版） | 🟡 中 | 僅研究助理有 | 同業比較頁快速提問 chip |
| 6 | `POST /peer-compare` | ⚪ 排工時 | 端點不存在 | 同業比較整頁 |
| 7 | `POST /history` | 🔴 高 | 端點不存在 | 研究助理 + 同業比較查詢後自動寫入對話紀錄 |
| 8 | `POST /subscriptions` | 🟡 中 | 端點不存在 | 通知中心「訂閱設定」tab — 使用者選擇追蹤公司 |

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

`doc_type` 對應前端標籤：`transcript`→法說逐字稿、`presentation`→法說簡報、`major_news`→重大訊息、`news`→新聞、`fin`→合併財報

---

## 4. `GET /chunk/{source_id}` — 引用原文（新端點）

### 對應功能

**研究助理 + 同業比較頁** → 引用追蹤器點擊展開卡片時，顯示 BQ 裡的實際文件片段與頁碼

### 目前狀態

前端 DocViewer 目前依賴 Citation 的 `snippet` 欄位（截 500 字），無法顯示完整段落或頁碼。

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

### 需求

請問 `/suggestions` 端點是否能加一個 `mode` 參數區分「研究助理」vs「同業比較」，讓回傳的提問建議更貼合兩個頁面的情境？

或者 R7 直接沿用同一個 `/suggestions`，前端自己加上「比較」前綴也可以，請告知哪種好維護。

---

## 6. `POST /peer-compare` — 同業比較（排工時）

### 對應功能

**同業比較頁** — 目前整頁為 hardcoded mock 資料，等 R3 排入工時後再一起對齊 schema。

### 屆時需要對齊

- Request：公司 A ticker、公司 B ticker、比較維度（財務 / 法說 / 估值 / 新聞）
- Response：KPI 對比（含引用接地）、比較摘要、法說重點、ReAct trace、矛盾警示

---

## 7. `POST /history` — 對話紀錄寫入

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

### 備註

- 若 R3 workflow 執行時能自動記錄（不需前端另外呼叫），請告知，前端可省略此呼叫
- /history 頁的「點擊跳轉」功能（帶 query 回對應頁面）前端已完成，只缺寫入端

---

## 8. `POST /subscriptions` — 訂閱設定儲存

### 對應功能

**通知中心（/notifications）→「訂閱設定」tab** — 使用者主動選擇要追蹤的公司後，呼叫此端點儲存訂閱清單；另需 `GET /subscriptions` 讓前端初始載入已訂閱的公司。

### 端點清單

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/subscriptions` | 取得目前使用者的訂閱清單 |
| `POST` | `/subscriptions` | 儲存（覆蓋）訂閱清單 |

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
3. 「追蹤通知」tab 顯示訂閱公司最新入庫的文件或新聞提示（doc_type / news），資料來源與顯示邏輯由 R3 / R4 決定

---

## 附：前端 Alert 資料流說明

```
R3 Watchdog → GET /alerts → 前端過濾 origin
  ├─ origin="research" → 研究助理頁監控面板 → POST /notifications/events 記錄
  └─ origin="peer"     → 同業比較頁監控面板 → POST /notifications/events 記錄

POST /contradiction → 前端 contraAlertStore（sessionStorage）
  └─ origin="contradiction" → 兩頁監控面板共用 → POST /notifications/events 記錄
```
