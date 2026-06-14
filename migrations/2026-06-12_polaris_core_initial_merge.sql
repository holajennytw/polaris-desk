-- Migration: polaris_core 首次資料合併（canonical 建置，SOP §4 補課）
-- Date:      2026-06-12
-- Author:    Wayne
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     polaris_core.chunks（新建）、polaris_core.financial_metrics（新建）、
--            polaris_core.colpali_pages、polaris_core.earnings_call_transcript、
--            polaris_core.r6_*（ontology / question bank / annotation guidelines）
--
-- 背景：polaris_core 至今為空，資料散在 polaris_dev_hbb97 / _jenny / _wayne。
-- 本 migration 把三個 dev dataset 的資料合併進 canonical。合併已在
-- `polaris_dev_wayne_staging` 完整彩排並通過 live smoke（VECTOR_SEARCH 自相似
-- top-1 score=1.0、filter 對映、寫入防呆），以下 SQL 直接取 staging 為來源。
--
-- ⚠️ 已知排除項（套用者請知悉）：
--   1. ✅ 已解決（2026-06-12）：jenny 的 96 筆 transcript chunks 原為 3072 維，
--      已用 scripts/reembed_pending_chunks.py（gemini-embedding-2 @768）重算並
--      併入 staging.chunks；隔離表 chunks_pending_reembed 保留原 3072 維向量
--      供稽核。語意檢索已 live 驗證（中文查詢 → VECTOR_SEARCH 命中正確頁面）。
--   2. polaris_dev_hbb97.03_financial_metric（25 列）疑為 financial_metrics 的
--      舊版重複，未納入；請 R4 確認後刪除或合併。
--   3. 題庫 20 檔股票中 15 檔（1216/2303/2357/2382/2412/2881/2882/2884/2886/
--      2891/2892/3037/3231/3711/6669）目前 **零 chunks** —— 本 migration 不解決
--      涵蓋率，需 R4 ingestion 補料（見 PR 描述的缺口清單）。

-- ── A. canonical chunks（SOP §4.1 schema；768 維）────────────────────────────
CREATE TABLE IF NOT EXISTS `polaris-desk-team.polaris_core.chunks` (
  chunk_id      STRING NOT NULL,
  ticker        STRING,
  doc_type      STRING,
  fiscal_period STRING,
  published_at  DATE,
  chunk_text    STRING,
  embedding     ARRAY<FLOAT64>
)
PARTITION BY published_at
CLUSTER BY ticker, doc_type;

INSERT INTO `polaris-desk-team.polaris_core.chunks`
  (chunk_id, ticker, doc_type, fiscal_period, published_at, chunk_text, embedding)
SELECT chunk_id, ticker, doc_type, fiscal_period, published_at, chunk_text, embedding
FROM `polaris-desk-team.polaris_dev_wayne_staging.chunks`;
-- 來源組成：247 列＝polaris_dev_hbb97.chunks 全量 151（presentation / news /
-- major_news）＋ jenny transcript chunks 96（已重算 768 維）；
-- 5 檔：2308/2317/2330/2454/3034，全部 768 維、chunk_id 無重複。

-- ── B. 向量索引（SOP §4.2）───────────────────────────────────────────────────
-- ⚠️ BigQuery 在 <5,000 列的表上不會物化向量索引；目前 151 列，VECTOR_SEARCH
-- 會自動退回暴力搜尋（功能正確、無索引加速）。先建好，資料夠了自動生效。
CREATE VECTOR INDEX IF NOT EXISTS chunks_emb_idx
ON `polaris-desk-team.polaris_core.chunks`(embedding)
OPTIONS(index_type = 'IVF', distance_type = 'COSINE');

-- ── C. financial_metrics（hbb97 schema 即 canonical；376 列）────────────────
CREATE TABLE IF NOT EXISTS `polaris-desk-team.polaris_core.financial_metrics` (
  ticker        STRING,
  fiscal_period STRING,
  metric_id     STRING,
  value         FLOAT64,
  unit          STRING,
  source_id     STRING,
  published_at  DATE
)
CLUSTER BY ticker, fiscal_period;

INSERT INTO `polaris-desk-team.polaris_core.financial_metrics`
SELECT ticker, fiscal_period, metric_id, value, unit, source_id, published_at
FROM `polaris-desk-team.polaris_dev_wayne_staging.financial_metrics`;

-- ── D. 其餘表（schema 照來源複製即可，建議用 bq cp 而非 CTAS，保留 schema）──
-- 套用者在 shell 執行（cp 不會動 partition/cluster 以外的東西，最低風險）：
--
--   bq cp -f polaris-desk-team:polaris_dev_wayne_staging.colpali_pages \
--            polaris-desk-team:polaris_core.colpali_pages
--   bq cp -f polaris-desk-team:polaris_dev_wayne_staging.earnings_call_transcript \
--            polaris-desk-team:polaris_core.earnings_call_transcript
--   for t in $(bq ls --format=json polaris-desk-team:polaris_dev_wayne_staging \
--       | python3 -c "import json,sys; [print(x['tableReference']['tableId']) for x in json.load(sys.stdin) if x['tableReference']['tableId'].startswith('r6_')]"); do
--     bq cp -f "polaris-desk-team:polaris_dev_wayne_staging.$t" "polaris-desk-team:polaris_core.$t"
--   done
--
-- （r6_* 共 32 表：ontology 24、question bank 8 類、annotation guidelines、
--   governance provenance —— 全部由 polaris_dev_wayne 維護，已彩排於 staging。）

-- ── E. 驗收（套用後跑，全部要過）────────────────────────────────────────────
-- 1) 列數對帳：
--    SELECT 'chunks' t, COUNT(*) n FROM `polaris-desk-team.polaris_core.chunks`
--    UNION ALL SELECT 'financial_metrics', COUNT(*)
--      FROM `polaris-desk-team.polaris_core.financial_metrics`;
--    -- 預期：chunks=247、financial_metrics=376
-- 2) 維度守門：
--    SELECT COUNT(*) FROM `polaris-desk-team.polaris_core.chunks`
--    WHERE ARRAY_LENGTH(embedding) != 768;   -- 預期 0
-- 3) 程式端 smoke（一般開發者帳號即可，唯讀）：
--    VECTOR_BACKEND=bigquery GCP_PROJECT=polaris-desk-team BQ_DATASET=polaris_core \
--      python -m pytest tests/test_vectorstore_impl.py -q
--    並跑一次 VECTOR_SEARCH 自相似查詢（取任一列 embedding 當 query，top-1
--    應為該列、score≈1.0）—— 同 staging 彩排步驟。
