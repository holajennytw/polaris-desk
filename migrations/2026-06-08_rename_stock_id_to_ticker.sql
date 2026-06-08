-- Migration: rename canonical column `stock_id` → `ticker`
-- Date:      2026-06-08
-- Author:    Wayne (R?)  ← 填你的角色
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 套用）
-- Scope:     polaris_core.chunks, polaris_core.financial_metrics
--            （任何其他帶 stock_id 欄的 canonical 表也要一併加進來）
--
-- 影響的下游契約（cutover 前須同步，否則 producer/consumer 欄名不一致）：
--   - R4 ingestion：寫入 row key `stock_id` → `ticker`
--     （scripts/poc_financial_extract.py、scripts/poc_transcript_ingest.py 已改）
--   - R3 watchdog 事件 JSON：`"stock_id"` → `"ticker"`（docs/R3_watchdog_開工指南.md）
--   - R7 frontend API JSON：`"stock_id"` → `"ticker"`（docs/R7_frontend_開工指南.md）
--   - 所有查詢的 cluster filter 條件 `WHERE stock_id = …` → `WHERE ticker = …`
--
-- ⚠️ Cutover 是破壞性的：欄名一改，舊 producer/consumer 立刻失敗。
--    建議流程：① 全下游改好並就緒 → ② 套用本 migration → ③ chunks 重建 VECTOR INDEX
--    → ④ 通知全團 canonical schema 版本更新。

-- ── 方案 A（首選，metadata-only，秒級、零掃描）─────────────────────────────
-- BigQuery `ALTER TABLE … RENAME COLUMN` 支援重命名 clustering 欄；保留資料與 partition。
ALTER TABLE `polaris-desk-team.polaris_core.chunks`
  RENAME COLUMN stock_id TO ticker;

ALTER TABLE `polaris-desk-team.polaris_core.financial_metrics`
  RENAME COLUMN stock_id TO ticker;

-- chunks 上有 VECTOR INDEX（chunks_emb_idx，建在 embedding 上，不含 stock_id）。
-- RENAME COLUMN 不動 embedding，理論上索引不受影響；若 R4 套用後發現索引狀態異常，
-- 重建一次（對齊 SOP §4.2）：
--   DROP VECTOR INDEX IF EXISTS chunks_emb_idx ON `polaris-desk-team.polaris_core.chunks`;
--   CREATE VECTOR INDEX chunks_emb_idx
--     ON `polaris-desk-team.polaris_core.chunks`(embedding)
--     OPTIONS(index_type = 'IVF', distance_type = 'COSINE');


-- ── 方案 B（fallback，若該 region/表型態不允許 RENAME clustering 欄）──────────
-- CREATE-AS-SELECT 重建（會掃全表、需重建索引；成本較高，僅在方案 A 失敗時用）：
--
-- CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.chunks`
-- PARTITION BY published_at
-- CLUSTER BY ticker, doc_type AS
-- SELECT
--   chunk_id,
--   stock_id AS ticker,
--   doc_type, fiscal_period, published_at, chunk_text, embedding
-- FROM `polaris-desk-team.polaris_core.chunks`;
-- -- 之後重建 chunks_emb_idx（見上）。financial_metrics 同理 CREATE OR REPLACE … SELECT stock_id AS ticker。
