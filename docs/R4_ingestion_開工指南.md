# R4 Ingestion 開工指南 — 把 102 份法說 PDF 灌進 BigQuery `polaris_core`

> **這份要解的問題**：全隊的關鍵路徑卡在「語料還沒進向量庫」。R4（資料工程師＝吳瑾瑜）把法說/財報 PDF → 解析 → 切塊 → embedding → 寫進 `polaris_core.chunks`，**一灌完，R3 檢索、R5 真分數、R6 Ontology 上線、R2 雲端 demo 全部解鎖**。
> **目標 DoD**：100 份法說稿入 `polaris_core`、可被 `Retriever` 查到（FR-001/G1）。本指南 = 最短路徑。

---

## 0. 現況盤點（好消息：地基都鋪好了）

| 項目 | 狀態 |
|---|---|
| **語料** | ✅ 已蒐齊：`07_ConferenceCall/` 102 份（2308台達17 / 2317鴻海29 / 2330台積32 / 2454聯發科24）＋ `06_Financial_Report/` 15 份（2330/2454/3034）|
| **PDF 型態** | ✅ **有文字層、免 OCR**（pdftotext 直接抽得到中文）。⚠️ 法說「Presentation」投影片圖表多、文字少 → W1 先吃**逐字稿 Transcript ＋ 財報**，圖表留給 ColPali（W2+）|
| **GCP** | ✅ 專案 `polaris-desk-team`、bucket `gs://polaris-desk-raw`、dataset `polaris_core`（空）已建；**你是 `polaris_core` OWNER**（唯一可寫的人）|
| **程式介面** | ✅ R2 已留好 stub：`VectorStore` 介面、`BigQueryStore`（三個方法待你填）、`GeminiClient.embed()`、`sanitize.py`、`bq-smoke` 自檢 |
| **你要做的** | ❌ 唯一缺口：**ingestion pipeline + 填 `BigQueryStore` 三個方法**（目前是 `raise NotImplementedError`）|

---

## 1. 環境設定（約 5 分鐘）

```bash
# 1) 認證走 ADC（金鑰絕不寫死、絕不進 git）
gcloud auth application-default login
gcloud config set project polaris-desk-team

# 2) 取得程式 + 建環境（Python 3.13）
cd polaris-desk && make setup        # 建 .venv + 裝依賴
cp .env.example .env                 # 若還沒有

# 3) 在 .env 填：你的個人 scratch + Gemini 金鑰（embedding 要用）
#    DEV_DATASET=polaris_dev_jenny     ← 換成你的英文名；先寫這裡測，驗過再進 core
#    GEMINI_API_KEY=<你的真實金鑰>      ← embed 要呼叫雲端，必填
```

> **鐵則（SOP §0）**：先寫進**自己的 `polaris_dev_<name>`** 測通，驗證 OK 再灌 `polaris_core`。embedding **只算一次、大家共讀**，別讓 7 個人各自重算（燒錢又不一致）。

---

## 2. 你要接的真實介面（別重造輪子）

R2 已把接口鋪好，你只要「填內容」+「實作 BigQueryStore」：

| 檔案 | 你怎麼用 |
|---|---|
| [`src/polaris/vectorstore/base.py`](../src/polaris/vectorstore/base.py) | `Document(id, content, embedding, company, period, metadata)` ← 你產生這個物件 |
| [`src/polaris/vectorstore/bigquery_store.py`](../src/polaris/vectorstore/bigquery_store.py) | **填這三個方法**：`add_documents` / `search` / `health_check`（現在都 raise）|
| [`src/polaris/llm/gemini.py`](../src/polaris/llm/gemini.py) | `GeminiClient().embed(text) -> list[float]`（`gemini-embedding-2`，768 維，維度由 `.env EMBEDDING_DIM` 控）|
| [`src/polaris/ingestion/sanitize.py`](../src/polaris/ingestion/sanitize.py) | 入庫前先過 `sanitize_text()` + `validate_for_ingestion()`（防投毒，已寫好）|
| [`docs/協作開發環境_SOP_v1.md`](協作開發環境_SOP_v1.md) §4 | BigQuery `chunks` 表 schema + 向量索引 + 成本護欄（權威）|

檢索層（R3）只透過 `VectorStore.search()` 拿資料，所以**你把 BigQueryStore 填對，R3/R2 一行都不用改**。

---

## 3. 最短路徑 Pipeline（6 步）

把這條寫成 `src/polaris/ingestion/run.py`（新檔，`python -m polaris.ingestion` 可跑）：

```
PDF → ① 解析文字 → ② sanitize → ③ 切塊(+metadata) → ④ embedding → ⑤ Document[] → ⑥ store.add_documents()
```

1. **解析**：`pdftotext`（已裝，最快）或 `pypdf`/`pdfplumber`（純 Python，加進 `[project.dependencies]`）。逐字稿/財報文字層完整，免 OCR。
2. **淨化**：每段過 `sanitize_text()`；`validate_for_ingestion(doc_id, content)` 回非空就 skip 該塊。
3. **切塊**：中文約 **500–800 字/塊 + 10–15% overlap**；**每塊帶 metadata**（見 §5），且保留 `source_id`（FR-003 逐句引用要溯源）。
4. **Embedding**：`GeminiClient().embed(text)`。**建議 batch**（`gemini.py` 已標 TODO：`embed_content(contents=[...])` 可一次多筆，省呼叫成本）。算完就存，**永不重算**。
5. **組 Document**：`Document(id=chunk_id, content=chunk_text, embedding=vec, company=stock_id, period=fiscal_period, metadata={doc_type, published_at, source_id})`。
6. **寫入**：`get_vector_store().add_documents(docs)` —— 即你下一步要實作的 `BigQueryStore.add_documents`。

> **W1 不必做滿**：先把 **TSMC + 鴻海的逐字稿 + 財報**（文字密）跑通端到端 1 份 → 再批次 100 份。ColPali 圖表、MOPS 爬蟲、新聞第 5 路是 W2–W3，別卡在這。

---

## 4. ⚠️ Schema 對照（這是最容易踩的雷）

`Document` 的欄名 ≠ SOP §4.1 BigQuery 表的欄名，**你要在 `BigQueryStore` 內做映射**（別改 `base.py` 介面）：

| `base.Document` | → BigQuery `polaris_core.chunks`（SOP §4.1）| 來源 |
|---|---|---|
| `id` | `chunk_id` STRING | `{stock_id}_{fiscal_period}_{doc_type}_{序號}` |
| `company` | `stock_id` STRING | 資料夾/檔名（2330, 2317…）|
| `period` | `fiscal_period` STRING | 檔名季別（見 §5）|
| `content` | `chunk_text` STRING | 切塊後文字 |
| `embedding` | `embedding` ARRAY<FLOAT64> | `GeminiClient.embed()` |
| `metadata["doc_type"]` | `doc_type` STRING | `transcript`/`presentation`/`financial_report` |
| `metadata["published_at"]` | `published_at` DATE | 季末日或檔名日期（**partition key，務必填**）|

R3 的 `Retriever` 會用 `filters={"company": "2330", "period": "2024Q3"}` 呼叫 `search()` → 你的 SQL 要轉成 `WHERE stock_id=@company AND fiscal_period=@period`，並盡量帶 `published_at` 範圍命中 partition。

---

## 5. metadata 怎麼推（從檔名/資料夾）

- **stock_id**：`07_ConferenceCall/2330_TSMC/` → `2330`；`06_Financial_Report/2330_202503.pdf` → `2330`。
- **fiscal_period**：
  - 法說檔名 `1Q24` / `2Q25` / `3Q24` → `2024Q1` / `2025Q2` / `2024Q3`。
  - 財報檔名 `2330_202503` = `YYYYMM` → 月份對季：`03→Q1, 06→Q2, 09→Q3, 12→Q4`，即 `202503→2025Q1`。
- **doc_type**：檔名含 `Transcript`→`transcript`；含 `Presentation`/`Results`(投影片)→`presentation`；`06_` 來源→`financial_report`。
- **published_at**：有日期欄（如 `_20250514_`）就用；否則用季末日（Q1→03-31…）。

> 對齊 [`graph/temporal.py`](../src/polaris/graph/temporal.py)：`period` 字串格式 **`2024Q3`**（R2 的 Temporal Anchoring 已用這格式過濾每季語料），**務必一致**，否則季別查詢撈不到。

---

## 6. 實作 `BigQueryStore` 三個方法（SQL 骨架）

```python
# health_check —— 先做這個，最快讓 `make bq-smoke` 轉綠（R2 的自檢已接好，PR #20）
def health_check(self) -> bool:
    self._get_client().query("SELECT 1").result()
    return True

# add_documents —— load_table_from_json 進 {dataset}.chunks（寫 dev_dataset 測，過了再 core）
def add_documents(self, docs):
    table = f"{self.settings.dev_dataset or self.settings.bq_dataset}.chunks"
    rows = [{
        "chunk_id": d.id, "stock_id": d.company, "fiscal_period": d.period,
        "doc_type": d.metadata.get("doc_type"),
        "published_at": d.metadata.get("published_at"),
        "chunk_text": d.content, "embedding": d.embedding,
    } for d in docs]
    self._get_client().load_table_from_json(rows, table).result()

# search —— BigQuery VECTOR_SEARCH（cosine，對齊 768 維）
def search(self, query_embedding, top_k=8, *, filters=None):
    # 用 VECTOR_SEARCH(TABLE {dataset}.chunks, 'embedding', (SELECT @q AS embedding),
    #     top_k=>@k, distance_type=>'COSINE')；filters 轉 WHERE stock_id/fiscal_period
    # 回傳 map 成 SearchResult(id, content, score, company, period, metadata)
    ...
```

**索引兩前提（SOP §4.2）**：①建 `CREATE VECTOR INDEX … OPTIONS(index_type='IVF', distance_type='COSINE')` 前，先確認 `asia-east1` 支援；②**BigQuery 不在 <5,000 列的表建向量索引** → 102 份切塊後通常會超過 5,000 列（沒超過則 `VECTOR_SEARCH` 自動退暴力搜尋，demo 仍可用，但要知道）。

---

## 7. 驗收清單（DoD，照順序勾）

- [ ] `make bq-smoke` **轉綠**（`health_check` 通 → 連線 OK）
- [ ] 在 **`polaris_dev_<你>`** 跑通：1 份 PDF → chunks 表有列、`embedding` 長度=768
- [ ] 手動 `search()` 一個查詢向量，回得到相關段落（分數合理）
- [ ] 批次 100 份法說稿入庫，列數 > 5,000（或記錄未達門檻、走暴力搜尋）
- [ ] 驗過再 **寫進 `polaris_core`**（你是唯一可寫者），建好 partition/cluster/向量索引
- [ ] **通知全隊「canonical 已就緒，可開始開發」**（SOP §4.3）→ 正式解鎖 R3/R5/R6/R2

---

## 8. 防雷 & 成本紀律

- **embedding 算一次重用**：別重跑全量 ingestion（SOP §0 鐵則）；上雲（W4）搬家用**匯出向量、不重算**。
- **金鑰走 ADC，不進 git**；`*_access.json`/`.env` 已在 `.gitignore`。
- **先 dev scratch 再 core**：`polaris_core` 全隊唯讀依賴，灌錯會擋到所有人。
- **PR 流程**：`BigQueryStore`/`ingestion/run.py` 走 PR（main 有必過 CI + R2 code-owner 批准），別直接 push main。新依賴（pypdf 等）加進 `pyproject.toml [project.dependencies]`。
- **離線 fallback 還在**：`VECTOR_BACKEND=pgvector` + `make db-up` 可本地跑（Demo Day 斷網備援，schema 見 [`scripts/init_pgvector.sql`](../scripts/init_pgvector.sql)）。

---

## 9. 一天開工順序（建議）

1. 上午：環境（§1）→ 填 `health_check` → `make bq-smoke` 綠（30 分鐘內有成就感）。
2. 中午：寫 `ingestion/run.py` 解析+切塊+embedding，**1 份 TSMC 逐字稿**端到端通到 `polaris_dev_<你>`。
3. 下午：填 `add_documents` + `search`，手動查一筆驗證；批次跑 100 份。
4. 收工前：建 `polaris_core` 表+索引、灌入、**發訊息通知全隊解鎖**。

> 卡住找誰：介面/CI → R2（施惠棋）；公司清單/季別/Ontology → R6（黃俊維）；檢索契約 → R3（謝劼恩）。
