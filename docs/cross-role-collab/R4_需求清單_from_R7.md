# R4 需求清單（R7 前端提出）

> 整理日期：2026-06-17｜撰寫：R7
> 本文件列出前端需要 R4 實作的 API 端點，含完整 request / response 規格。

---

## 1. `GET /library` — 研究資料庫文件列表

### 背景

前端有一頁「研究資料庫 `/library`」，讓使用者看到目前 BQ 裡有哪些文件已建索引，幫助他們了解可以查詢哪些公司、哪些期別的法說稿與財報。

**資料已在 BQ**：`chunks` 表目前有 6,885 筆（20 檔 ticker），不需要新 ingest，只需要一個唯讀端點把資料整理成文件列表。

### R4 已完成 ingestion，為什麼還需要這個端點？

R4 的 ingestion 工作（PDF → chunk → 向量化 → 寫入 BQ）已完成，`chunks` 表有 6,885 筆資料。**這個端點不是要求 R4 重做 ingestion**，而是補上「讀端點」：

- `GET /events` → R4 的 events 表讀端點（已有）
- `GET /financials` → R4 的 financial_metrics 表讀端點（已有）
- `GET /companies` → R4 的 company_dim 表讀端點（已有）
- **`GET /library` → R4 的 chunks 表讀端點（缺這一個）**

**為什麼前端不能直接讀 `chunks`？**

依憲法 + 資料表欄位表規定，`chunks` 有 `owner`/`confidential` 存取控制，前端不可直連 BQ，必須由後端帶 `viewer` 過濾後才能讀（同現有 `/research`、`/ask` 的做法）。

### 背景說明

把 chunk 還原成「文件列表」需要對 `chunks` schema 的了解：

- **如何判斷「一份文件」**：多個 chunk 屬於同一份 PDF，需要 GROUP BY（`ticker + fiscal_period + doc_type`，或以 `chunk_id` 前綴判斷）
- **頁數計算**：chunk 的切法與頁碼對應邏輯
- **ingested 狀態**：哪些文件完整入庫、哪些部分入庫

前端不直連 BQ，也無法自行判斷 chunks 的文件邊界；此端點由熟悉 ingestion 流程的角色實作較合適。

### 端點規格

```
GET /library
```

無 query params（初版全量回傳，前端自行 filter）。

### 期望 Response

```json
{
  "stats": [
    { "label": "已建索引文件", "value": "42 份" },
    { "label": "涵蓋公司", "value": "20 家" },
    { "label": "最後更新", "value": "2026-06-16" }
  ],
  "types": [
    { "id": "transcript",   "label": "法說逐字稿", "count": 12 },
    { "id": "major_news",   "label": "重大訊息",   "count": 24 },
    { "id": "news",         "label": "新聞",        "count": 6  }
  ],
  "docs": [
    {
      "id":         "2330-2026Q1-transcript",
      "title":      "台積電_2026Q1_法說會逐字稿",
      "kind":       "transcript",
      "company":    "台積電",
      "period":     "2026Q1",
      "pages":      42,
      "size":       "2.1 MB",
      "source_key": "2330",
      "ingested":   true,
      "time":       "2026-04-18"
    }
  ]
}
```

### 欄位規格

**`stats`**（統計卡，彈性）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `label` | string | 顯示標籤 |
| `value` | string | 顯示數值（字串，含單位） |

**`types`**（文件類型分頁 tab）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | string | `doc_type` 原始值（`transcript` / `major_news` / `news`…） |
| `label` | string | 中文顯示名 |
| `count` | number | 該類型文件數 |

**`docs`**（文件列表，一筆 = 一份文件）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | string | 唯一識別，建議 `{ticker}-{fiscal_period}-{doc_type}` |
| `title` | string | 文件顯示名稱 |
| `kind` | string | `doc_type` 原始值 |
| `company` | string | 中文公司名（JOIN `company_dim`） |
| `period` | string | 財報期別，如 `2026Q1`；無期別文件可填空字串 |
| `pages` | number | 頁數（無資料填 0） |
| `size` | string | 檔案大小字串，如 `"2.1 MB"`；無資料填空字串 |
| `source_key` | string | ticker，前端備用 |
| `ingested` | boolean | 是否完整入庫 |
| `time` | string | 文件發布日或入庫日（`YYYY-MM-DD`） |

### 資料來源建議

```sql
-- 一份文件 = (ticker, fiscal_period, doc_type) 組合
SELECT
  ticker,
  COALESCE(fiscal_period, "") AS fiscal_period,
  doc_type,
  MIN(published_at)           AS published_at,
  COUNT(*)                    AS chunk_count
FROM `polaris-desk-team.polaris_core.chunks`
GROUP BY ticker, fiscal_period, doc_type
ORDER BY published_at DESC
```

`pages`、`size` 若 chunks 沒有直接欄位，可先回傳 0 / 空字串，前端不影響顯示。

### 前端現況

- `/library` 頁面 UI 已完成（表格、類型 tab、ticker 篩選 tab）
- 目前呼叫 `GET /library`，端點不存在時頁面空白
- 等 R4 交付此端點後，前端無需修改即可顯示真實資料

---

## 優先級

| # | 端點 | 優先 | 狀態 |
|---|------|------|------|
| 1 | `GET /library` | 🟡 中 | 端點不存在，UI 已就緒 |
