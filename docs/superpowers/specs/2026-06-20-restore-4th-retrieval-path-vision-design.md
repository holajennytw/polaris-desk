# 設計：補回第 4 路「ColPali 視覺檢索」——接上既有 `colpali_pages`

- **日期**：2026-06-20
- **狀態**：設計待 review
- **作者**：Wayne（與 Claude 協作）
- **關聯決議**：逆轉 TD-01（2026-06-14 cut ColPali 檢索整合）→ 記為 **TD-02**（需 PM 簽核）

> ⚠️ **重要更正**：本案初版設計（Gemini vision-OCR 轉文字進 768 庫）前提錯誤，已作廢。
> 經 BigQuery 查證，R4 資料端**早已**用 ColPali 處理圖表頁並入庫
> （`polaris_core.colpali_pages`，5701 頁），只是 R3 檢索端從未接上。本案改為
> **接上既有 colpali 資料**，而非重做一套文字路。

---

## 1. 背景（查證後事實）

`polaris_core.colpali_pages` 真實存在且有料（`bq show` / 抽樣查證 2026-06-20）：

| 項目 | 內容 |
|---|---|
| 規模 | **5701 頁**法說簡報（doc_type 全為 `presentation`），**20 tickers**、23 個 fiscal period |
| 向量 | 每頁**單一 128 維** ColPali 向量（patch 池化後）；`n_patches=1031`（固定常數，僅 metadata） |
| schema | `page_id, ticker, fiscal_period, doc_type, source_file, page_num, event_date, published_at, embedding(REPEATED FLOAT, len=128), n_patches, fetched_at` + `event_key/source_key/published_year/published_month/published_yyyymm`（2026-06-18 migration 補） |
| 形態 | **128 維 cosine**——patch 矩陣未存，故**非** MaxSim late-interaction |
| 現狀 | repo 內**無任何程式讀它**（R4 入庫、R3 未接）；產生它的 ColPali 模型程式在 repo 外（R4 Colab/GPU） |

對照 [`retriever.py:7`](../../../src/polaris/retrieval/retriever.py)「ColPali 已於 G3 前評估後 cut（TD-01）」——
該註解只反映 **R3 檢索端**的決定，**資料端事實並非如此**。這是 R4↔R3 的脫節。

`CitationOrigin` Literal（[`state.py:23`](../../../src/polaris/graph/state.py)）**早已含 `"colpali"`**，
各處 `_CITATION_ORIGINS` 集合亦然——scaffolding 本就為此預留。

## 2. 目標 / 非目標

**目標**
- 接上既有 `colpali_pages`，補回 4-way 的第 4 路（視覺檢索），處理圖表題（場景 3）。
- **Phase 1**：ColPali 檢索 + 命中率 eval（沿用 TD-01 門檻 **≥70%**）。
- **Phase 2**：對撈到的頁讀數字回答（render PDF 頁圖 → vision LLM）。
- **不改變現有資料架構**：`colpali_pages` 已存在且只讀；768/cosine `chunks` 庫完全不動。

**非目標**
- 不重做 vision-OCR 轉文字（初版作廢）。
- 不改 `chunks` 庫 schema、不改 `gemini-embedding-2`(768)。
- Phase 1 不含「讀數字回答」（移至 Phase 2）。
- 不重建 patch 級多向量 / MaxSim（資料端只存了池化 128 維，沿用之）。

## 3. 設計決策

| 決策點 | 選定 | 理由 |
|---|---|---|
| 視覺路資料 | **接既有 `colpali_pages`**（非重做 vision-OCR） | R4 已入庫 5701 頁；重用已付出的 GPU/ingestion 成本 |
| 來源標記 | **`origin="colpali"`**（Literal 既有值，零變更） | scaffolding 已預留；如實反映 ColPali 來源 |
| 查詢端編碼 | **R4 提供 ColPali query encoder**（query→128 維，注入當 embedding_fn） | 128 維在 ColPali 空間，gemini-embedding-2 不通用 |
| 接法範圍 | **Gated**：圖表題走專用 ColPali retriever，不混進文字排序 | 視覺頁無文字、分數尺度異於文字塊，硬 merge 噪音大 |
| 階段切分 | **兩階段**：P1 檢索+命中率；P2 vision 讀數字回答 | TD-01 門檻講「檢索命中率」；P1 不卡 PDF 存放 |
| eval 場景 3 | `_run_visual` 改跑**真 ColPali 檢索**（取代 NotImplementedError） | 量測 ≥70% 命中率 |
| 資料庫 | **新 `BigQueryColpaliStore`**（VECTOR_SEARCH 於 colpali_pages，128 維） | 與 `chunks` 庫分離；不動既有 store |

## 4. 架構與資料流

```
查詢端（Phase 1）
  query ──► R4 ColPali query encoder ──► 128 維 query 向量
             └─► BigQueryColpaliStore.search（VECTOR_SEARCH cosine 於 colpali_pages，
                  filter: ticker / fiscal_period / viewer）
                  └─► top-k 頁 ──► Citation(origin="colpali",
                                            source_id=page_id,
                                            snippet=「{ticker} {fiscal_period} 第 {page_num} 頁圖表（{source_file}）」,
                                            company=company_name(ticker))

分派（gated）
  場景 3（圖表題）──► ColpaliRetriever（上方流程）
  其餘場景        ──► 既有 5 節點 workflow（BM25 + 768 向量 + Cohere Rerank），不混入

回答端（Phase 2，後續）
  撈到的頁 ──► 由 source_file 找原始 PDF ──► render 該頁圖（pdftoppm）
            ──► Gemini vision 讀圖表數字 ──► 回答 + 接地「第 N 頁圖表」
```

## 5. 變更清單

### Phase 1（核心：檢索 + 命中率）

| # | 檔案 | 變更 | 動資料架構？ |
|---|---|---|---|
| 1 | `src/polaris/vectorstore/bigquery_colpali_store.py`（新） | VECTOR_SEARCH（cosine）於 `colpali_pages`，128 維；注入 R4 query encoder 當 embedding_fn；回 `SearchResult`（metadata 帶 ticker/fiscal_period/page_num/source_file，`origin="colpali"`） | 否（只讀既有表） |
| 2 | `src/polaris/retrieval/`（新 `ColpaliRetriever` 或 HybridRetriever 加 gated 通道） | 場景 3 專用；query encoder 缺席時優雅 skip（CI friendly） | 否 |
| 3 | [`eval/runner.py`](../../../src/polaris/eval/runner.py) | `_run_visual` 改跑真 ColPali 檢索；修正過時「W3 排程」註解 | 否 |
| 4 | [`retriever.py:386`](../../../src/polaris/retrieval/retriever.py) `_citation_origin` | 確保 `"colpali"` 正確映射（已在集合內，驗證即可） | 否 |
| 5 | `tests/`（test_eval_pipeline 場景 3 改驗真檢索；新增 ColpaliStore / ColpaliRetriever 測試） | 無 query encoder 時 skip；有 stub encoder 時驗檢索與 origin | 否 |

> 注意：`state.py` / `stubs.py` 的 `CitationOrigin` 與集合**已含 `"colpali"`**，無需新增。

### Phase 2（回答：讀數字）— 後續，先確認 PDF 存放

| # | 項目 | 變更 |
|---|---|---|
| 6 | PDF 來源解析 | 由 `source_file` 定位原始 PDF（GCS？本機？需 R4 確認） |
| 7 | 頁圖 render + vision 讀數字 | `pdftoppm` render → Gemini 多模態讀 → 回答接地；prompt 禁編造 |

### 文件
| # | 檔案 | 變更 |
|---|---|---|
| 8 | 憲法 / [`G3_readiness.md`](../../G3_readiness.md) / runner 註解 | 記 **TD-02**（retrieval 回 4-way，接既有 colpali_pages），需 PM 簽核 |

## 6. 優缺點

**優點**
- **重用既有資料**：5701 頁 ColPali 向量已入庫，GPU/ingestion 成本已付。
- **零資料架構變更**：`colpali_pages` 已存在且只讀；`chunks` 768 庫不動。
- **origin 零新增**：`"colpali"` Literal 與集合早已預留。
- **Gated 不污染文字檢索**：既有 3-path 行為與測試零回歸。
- **CI 友善**：query encoder 缺席時 skip，確定性可重現。

**缺點 / 風險**
- 🔴 **依賴 R4 query encoder**：須與 page 端**同模型同池化**，否則向量不同空間 → 檢索無意義。
- 🟡 **池化削弱 ColPali**：只存 128 維池化向量、丟 patch 矩陣 → late-interaction 優勢沒了，命中率 ≥70% 能否過為未知。
- 🟡 **Phase 2 需原始 PDF**：表內無文字/圖，`source_file` 只是檔名 → 回答需定位 PDF + render，依賴 R4 存放資訊。
- 🟡 **資料品質瑕疵**：抽樣見 `fiscal_period="1936Q2"`（event_date 2025-06-05）等疑似 temporal 解析錯誤 → 影響 period filter，落地前需與 R4/R6 核對。
- 🟡 **重啟 TD-01**：逆轉已記錄決議，需 PM 簽核 + 文件更新（TD-02）。

## 7. 驗收標準

**Phase 1**
- 場景 3 圖表題：ColPali 檢索能撈回正確簡報頁，**命中率 ≥70%**（沿用 TD-01 門檻）。
- Citation `origin="colpali"`、帶 ticker/fiscal_period/page_num 接地；既有 3-path 與測試無回歸。
- 無 query encoder 時 CI 確定性可重現（通道 skip）。

**Phase 2**
- 對撈回頁能讀出圖表數字並正確回答，接地「第 N 頁圖表」，不編造。

## 8. 風險與緩解

| 風險 | 緩解 |
|---|---|
| query encoder 與 page 端不一致 | 落地前與 R4 確認同模型同池化；用少量已知頁做 round-trip 自檢（query=該頁標題應撈回該頁） |
| 池化後命中率 < 70% | 沿用 TD-01 門檻：未達即回報，評估是否改存 patch 多向量（資料端重做） |
| Phase 2 PDF 取不到 | P1 與 P2 解耦；P1 先交付檢索價值，P2 待 PDF 來源確認 |
| fiscal_period 等欄位瑕疵 | 與 R4/R6 核對 temporal 對映；filter 容錯 |
| 逆轉 TD-01 未經同意 | 先取得 PM 簽核再落地，記 TD-02 |

## 9. 已定案 / 待確認

**已定案（2026-06-20）**
- 接既有 `colpali_pages`（非 vision-OCR 重做）；`origin="colpali"`。
- Gated（場景 3 專用）+ 兩階段（P1 檢索 / P2 回答）。
- 新 `BigQueryColpaliStore`，128 維 cosine，只讀既有表。

**待確認（落地前）**
- R4 交付 query encoder 形式（in-process 模型 vs 推論端點）與**池化方式一致性**。
- Phase 2：原始 PDF 存放位置（GCS / 本機 / R4 提供）。
- `colpali_pages` 資料品質（fiscal_period 等）與 R4/R6 核對。
- PM 對 TD-02（4-way 復原）的正式簽核。
