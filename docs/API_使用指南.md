# Polaris Desk API 使用指南

> **給誰**：前端（R7）、串接 Polaris Desk 後端的任何人。
> **這是什麼**：`src/polaris/api.py` 這支 thin FastAPI 的所有 HTTP 端點怎麼呼叫、參數、回應形狀、範例。
> **權威契約＝ OpenAPI**：服務啟動後 `GET /openapi.json`（機器可讀）、`GET /docs`（Swagger 互動頁）是**自動產生、永不過期**的契約。本檔是人讀導覽；欄位有出入時**以 `/openapi.json` 為準**。

---

## 0. 啟動 / Base URL

```bash
# 本地
uv venv --python 3.13 && uv pip install -e ".[dev]"
python -m polaris.api          # 監聽 $PORT（預設見啟動日誌），如 http://localhost:8080
```

- 互動文件：`http://localhost:8080/docs`
- 健康探針：`GET /healthz`（本地）、`GET /health`（雲端；Cloud Run 的 GFE 會攔截 `/healthz`）。
- **CORS**：預設只允許 `http://localhost:3000`、`http://localhost:8501`（非萬用 `*`）。前端網域要加進 `CORS_ORIGINS`（逗號分隔，`.env`）。

## 1. 端點總表

| 方法 | 路徑 | 用途 | 需金鑰? |
|---|---|---|---|
| GET | `/health`・`/healthz` | 健康探針 | 否 |
| POST | `/ask` | 單輪問答（答案＋引用＋合規＋trace） | 引擎有金鑰才走真模型；無金鑰走 fallback |
| POST | `/research` | Deep Research ReAct（多步研究） | 同上 |
| GET | `/alerts` | Watchdog 事件 → Alert Inbox | 否（mock 事件，token-free） |
| GET | `/notifications` | 通知收件匣列表＋未讀數 | 否 |
| POST | `/notifications/events` | 發布事件進通知管線 | 否 |
| POST | `/notifications/{id}/read` | 標已讀 | 否 |
| POST | `/notifications/reset` | 重置收件匣（demo/測試） | 否 |
| GET | `/companies` | 公司清單（ticker→名稱/產業） | 否（讀 `polaris_core`） |
| GET | `/financials` | 財務指標 | 否（讀 `polaris_core`） |
| GET | `/events` | 事件流 / 時間軸 | 否（讀 `polaris_core`） |

> **取數分層**：語意問答 → `/ask`、`/research`（後端處理 embedding／存取控制／引用接地）。結構化資料 → `/companies`、`/financials`、`/events`（直讀 `polaris_core`，**不碰 `chunks`**——機密欄由問答端點的 retriever 過濾）。

---

## 2. 研究 / 問答

### `POST /ask`
單輪問答，跑 5 節點 workflow。

**Request**
```jsonc
{
  "query": "台積電最近兩季毛利率？",   // 必填，非空白
  "viewer": "analyst_A"                // 選填；存取控制身分（issue #32），省略=只看公開文件
}
```
**Response** `200`
```jsonc
{
  "answer": "……（已過合規）",
  "compliance_status": "passed",        // passed / blocked / unknown
  "citations": [
    { "source_id": "2330-2025Q4-c003", "snippet": "毛利率 59%…", "origin": "embedding" }
  ],
  "trace": [
    { "node_name": "planner", "status": "ok", "elapsed_ms": 12,
      "input_keys": ["query"], "output_keys": ["plan"], "error_message": null }
  ]
}
```
- 空白 `query` → `422`。

```bash
curl -s localhost:8080/ask -H 'content-type: application/json' \
  -d '{"query":"台積電最近兩季毛利率？"}'
```

### `POST /research`
Deep Research ReAct loop（≤6 迴圈 / ≥3 引用 / 過合規）。

**Request**：`{ "question": "...", "viewer": "..."(選填) }`
**Response** `200`
```jsonc
{
  "final_answer": "- 論點…（來源：sid）",
  "evidence":   [ { "source_id": "…", "snippet": "…", "origin": "embedding" } ],
  "react_steps":[ { "thought": "…", "action": "search",
                    "action_input": "台積電 毛利率", "observation": "取得引用…" } ],
  "status": "answered",                 // answered / exhausted
  "compliance_status": "passed"
}
```
- 空白 `question` → `422`。

---

## 3. 通知 / 警示

### `GET /alerts`
跑 mock MOPS 事件 → Watchdog → `WatchdogAlert[]`（token-free，CI 可測）。
```jsonc
[
  { "event_id": "mops-2330-…", "ticker": "2330",
    "summary": "事件合規摘要（0 買賣建議）",
    "compliance_status": "passed",      // passed / blocked
    "severity": "info",                 // info / watch / alert
    "evidence": [ { "source_id": "…", "snippet": "…", "origin": "news" } ] }
]
```

### `GET /notifications`
收件匣列表（`created_at` 倒序）＋未讀數。Query：`ticker`、`type`。
```jsonc
{ "items": [ /* Notification[] */ ], "unread_count": 3, "delivery_failures": [] }
```
- `POST /notifications/events`：發布事件進真實管線，回 `PublishOutcome`（壞事件回 `status=rejected`，仍 HTTP 200）。
- `POST /notifications/{id}/read`：標已讀；查無 → `404`。
- `POST /notifications/reset`：重置收件匣（in-memory 單例換新）。

---

## 4. 結構化資料（直讀 `polaris_core`）

> 欄位定義與可 filter 的值見 [`docs/R7_前端_資料表欄位表.md`](./R7_前端_資料表欄位表.md)。`published_at` 為 ISO 日期字串（`YYYY-MM-DD`）。

### `GET /companies`
canonical 公司清單（`company_dim`，~20 列；ticker→名稱/產業）。無參數。
```jsonc
[
  { "ticker": "2330", "company_name": "台積電", "english_name": "Taiwan Semiconductor Manufacturing Company",
    "market": "上市", "industry_id": "IND_FOUNDRY", "industry_name": "晶圓代工",
    "is_financial": false, "aliases": "台積電,TSMC,2330" }
]
```

### `GET /financials`
財務指標（`financial_metrics`），時間倒序。

| Query | 說明 | 例 |
|---|---|---|
| `ticker` | 股票代號 | `2330` |
| `period` | 財報期別 | `2025Q4` |
| `metric` | 指標代碼 | `revenue`、`eps`、`net_income`…（14 種，見欄位表） |
| `limit` | 回傳上限 1–1000（預設 200） | `50` |

```jsonc
// GET /financials?ticker=2330&metric=eps&limit=3
[
  { "ticker": "2330", "fiscal_period": "2026Q1", "metric_id": "eps",
    "value": 22.08, "unit": "新台幣元/股", "source_id": "…", "published_at": "2026-04-17" }
]
```
```bash
curl -s "localhost:8080/financials?ticker=2330&metric=eps&limit=3"
```
- `limit` 超出 1–1000 → `422`。一檔一期會有多個 `metric_id`，用 `(ticker, fiscal_period, metric_id)` 當 key 取值。

### `GET /events`
事件流（`events`），時間倒序。做公司動態時間軸 / 收件匣。

| Query | 說明 | 例 |
|---|---|---|
| `ticker` | 股票代號 | `2330` |
| `type` | 事件型別（對映 `event_type`） | `monthly_revenue`、`earnings_call`、`major_news`、`news` |
| `limit` | 回傳上限 1–1000（預設 200） | `100` |

```jsonc
// GET /events?ticker=2330&type=monthly_revenue&limit=2
[
  { "event_id": "…", "ticker": "2330", "event_type": "monthly_revenue",
    "published_at": "2026-05-31", "title": "台積電 2026年05月營收報告", "source_url": "https://mops…" }
]
```
- 列表回應**不含** `body` / `raw_json`（可能很大）；需要全文細節再查原表 / 開細節端點。

---

## 5. 慣例與防雷

- **合規（憲法 NFR-031）**：任何回應都不含買賣建議；`compliance_status=blocked` 代表被合規閘門擋下，前端要明確標示。
- **引用接地**：每個數字/結論都帶 `source_id`（問答）或 `source_id`/`source_url`（事件）——前端務必顯示來源。
- **欄位名一字不差**：`source_id` / `compliance_status` / `react_steps` / `fiscal_period` … 直接照用，別自行改名。
- **無金鑰也能跑**：`/ask`、`/research` 在無 Gemini 金鑰時走確定性 fallback（token-free），前端開發/CI 不被金鑰卡住。
- **契約變更**：改任何欄位＝ R2/R3/R7 一起改，並重生前端的 OpenAPI 型別（`openapi-typescript`）。

---

*對應程式碼：[src/polaris/api.py](../src/polaris/api.py)（端點）、[src/polaris/structured_store.py](../src/polaris/structured_store.py)（結構化讀層）。最後更新 2026-06-17。*
