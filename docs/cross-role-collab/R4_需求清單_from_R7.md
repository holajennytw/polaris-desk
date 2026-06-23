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

---

## 2. ColPali ↔ R7 前端整合問題（2026-06-23 新增）

> **背景**：R4 正在完成 ColPali query encoder（Issue #133）。`v_colpali_pages_semantic` 已可在 BQ 看到，代表整頁視覺向量已部署。R7 需要在 R4 完成 HTTP 端點前確認以下兩個設計問題，避免前端大改。

### 問題 1：`POST /research` 的 ColPali 結果從哪個欄位回來？

前端目前只處理 `evidence[]` 陣列。ColPali 結果有兩種可能：

| 情境 | 後端做法 | R7 影響 |
|------|---------|---------|
| **A（建議）** | ColPali 頁面結果合併進現有 `evidence[]`，加一個欄位標示來源（如 `origin: "colpali"`） | R7 幾乎不用改，`CitationList` 自動顯示 |
| **B** | 另開新欄位 `visual_pages: []` | R7 需新增 section + DocViewer 圖片模式 |

**請確認選哪個情境**，R7 偏好情境 A（統一資料流）。

### 問題 2：`GET /chunk/{source_id}` 是否也接受 ColPali `page_id`？

前端 `handleOpenDoc(cite)` 是統一入口，拿到任何 `source_id` 都打同一個端點。

- 若 R4 的 ColPali 頁面用 `page_id`（如 `page-2330-2026Q1-p7`）作為 source_id，**希望 `/chunk/{source_id}` 後端能統一判斷前綴，查 `chunks` 或 `colpali_pages`，回傳相同 response schema**
- 若 R4 決定另開 `/page/{page_id}`，請告知，R7 需要在 `handleOpenDoc` 加前綴判斷邏輯

---

## 3. `v_chunks_embedding_semantic` View 說明請求（2026-06-23 新增）

> **背景**：R7 在 BQ Console 看到此 view，但 `docs/frontend/資料表欄位表.md`（2026-06-21）沒有記錄。

**請 R4 說明**：

1. 這個 view 是誰建的、什麼時候建的？
2. 用途是什麼？（推測是 `v_chunk_semantic` 的帶 embedding 版，供 ColPali / 混合搜尋用？）
3. 前端是否需要知道這個 view？或純粹是後端內部用？
4. 欄位表需要更新嗎？

**請 R4 回應後，R7 更新 `docs/frontend/資料表欄位表.md`。**

---

## 4. KPI 卡片排序偏好（2026-06-23 R4 feedback）

研究助理 + 同業比較的 KPI 卡區塊，**期望顯示順序**：

```
營收 → 毛利率 → 營業利益率
```

**目前狀況**：
- 研究助理 fallback（`useFinancials`）只顯示「月營收 YoY」+ 「累計 YoY」，沒有毛利率
- 同業比較 `PeerKpiGrid` 順序為：毛利率 → 營業利益率 → 營收 YoY

**涉及分工**：
- `gross_margin`/`operating_margin` BQ 無欄位，需 R3 在 `POST /research` + `POST /peer-compare` workflow 內計算後附在 `kpis[]` 回傳
- R4 如有建議的 metric_id 命名或計算口徑，請補充（前端以後端回傳為準，不自行計算）

---

## 優先級

| # | 項目 | 優先 | 狀態 |
|---|------|------|------|
| 1 | `GET /library` | 🟡 中 | 端點不存在，UI 已就緒 |
| 2 | ColPali 整合情境確認（問題 1 + 2） | 🟡 中 | 等 #133 完成前需確認 |
| 3 | `v_chunks_embedding_semantic` 說明 | 🟡 中 | 欄位表待更新 |
| 4 | KPI 卡排序 | ⚪ 低 | 等 R3 交付 kpis[] 後前端調整 |
