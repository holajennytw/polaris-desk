-- Migration: dedupe polaris_core.chunks 的 news 列
--            （8 組真重複列收斂為 1 列 + 1 組 chunk_id 撞號改名）
-- Date:      2026-06-22
-- Author:    Jenny
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1
--            套用，套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）。
--            本檔會重寫 chunks 本表（CREATE OR REPLACE TABLE），非單純 view，
--            套用前務必先跑 Step 0 備份，且套用後需重建 vector index（Step 3）。
-- Scope:     polaris-desk-team.polaris_core.chunks（重寫本表，列數減少 8）
-- 觸發：     套用 migrations/2026-06-22_create_chunks_embedding_semantic_view.sql
--            後驗證列數發現 6885 → view 多出 18（即 chunks 本表已有 9 組
--            chunk_id 重複），逐一比對後發現：
--              - 8 組（news_c24c15f8.../news_33d3fa7c.../news_b627ca39.../
--                news_5dd609b4.../news_6ebcbc60.../news_da1d5ddb.../
--                news_fbf58f43.../news_d4fa803a...）整列（含 chunk_text /
--                embedding）逐 byte 相同，確認為同一篇新聞重複 ingest 兩次，
--                可安全收斂為 1 列。
--              - 1 組（news_09005085bf3706d8）是 chunk_id 撞號，非真重複：
--                同一篇新聞（2330 ADR 大漲帶動台股）被同時標記給 ticker=2308
--                與 ticker=2330，兩列其餘欄位皆不同（ticker 不同），但
--                chunk_id 雜湊未把 ticker 算進去，導致兩篇「内容相同但
--                ticker 標籤不同」的列撞號。若直接 DISTINCT 收斂會誤刪
--                ticker=2308 那筆真實資料，故改用 UPDATE 為其重新命名
--                chunk_id（保留兩筆，不刪除）。
--            根因（chunk_id 雜湊未納入 ticker）屬 ingestion pipeline 問題，
--            本檔僅修資料，不改 ingestion 程式碼；ingestion 端需另開 issue
--            修正 chunk_id 生成邏輯，避免未來同篇跨 ticker 新聞再次撞號。
--
-- ⚠️ 套用者請知悉：
--   1. 本檔非冪等：Step 1 UPDATE 條件命中後 chunk_id 已改名，重跑時
--      WHERE chunk_id = 'news_09005085bf3706d8' AND ticker = '2308' 不會再
--      命中（安全，不會重複改名/出錯），但 Step 2 CREATE OR REPLACE TABLE
--      重跑是安全的（SELECT DISTINCT 對已去重的表不會再變動列數)。
--   2. CREATE OR REPLACE TABLE 会重建 chunks 本表，必须在 Step 2 的
--      CREATE OR REPLACE TABLE 陈述句中手动指定与原表一致的
--      PARTITION BY / CLUSTER BY，否则会丢失分区与聚簇设定。
--   3. CREATE OR REPLACE TABLE 会清掉既有的 vector index，Step 3 必须重建
--      （沿用 migrations/2026-06-12_polaris_core_initial_merge.sql 的設定）。
--   4. Step 0 备份表 chunks_backup_20260622 请保留至少一个 sprint，确认无误
--      后再由 R1 决定是否清除。

-- ── Step 0：備份（套用前必跑，套用後留存供回退）───────────────────────────
CREATE TABLE IF NOT EXISTS `polaris-desk-team.polaris_core.chunks_backup_20260622`
AS SELECT * FROM `polaris-desk-team.polaris_core.chunks`;

-- ── Step 1：修撞號（保留兩筆，僅改 ticker=2308 那筆的 chunk_id）───────────
UPDATE `polaris-desk-team.polaris_core.chunks`
SET chunk_id = 'news_09005085bf3706d8_2308'
WHERE chunk_id = 'news_09005085bf3706d8'
  AND ticker = '2308';

-- ── Step 2：收斂 8 組真重複列（整表 DISTINCT 重寫，保留 PARTITION/CLUSTER）─
CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.chunks`
PARTITION BY published_at
CLUSTER BY ticker, doc_type
AS
SELECT DISTINCT *
FROM `polaris-desk-team.polaris_core.chunks`;

-- ── Step 3：重建 vector index（CREATE OR REPLACE TABLE 會清掉舊索引）──────
CREATE VECTOR INDEX IF NOT EXISTS chunks_emb_idx
ON `polaris-desk-team.polaris_core.chunks`(embedding)
OPTIONS(index_type = 'IVF', distance_type = 'COSINE');

-- ── 套用後驗證 ──────────────────────────────────────────────────────────
-- 預期：6885 - 8 = 6877 列；chunk_id 應無重複；
-- news_09005085bf3706d8_2308 應存在且 ticker=2308；
-- news_09005085bf3706d8 應只剩 ticker=2330 那一筆。
-- SELECT COUNT(*) AS n FROM `polaris-desk-team.polaris_core.chunks`;
-- SELECT chunk_id, COUNT(*) AS n FROM `polaris-desk-team.polaris_core.chunks`
-- GROUP BY chunk_id HAVING n > 1;
-- SELECT chunk_id, ticker FROM `polaris-desk-team.polaris_core.chunks`
-- WHERE chunk_id IN ('news_09005085bf3706d8', 'news_09005085bf3706d8_2308');
