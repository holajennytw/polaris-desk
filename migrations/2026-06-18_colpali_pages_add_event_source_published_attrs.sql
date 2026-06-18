-- Migration: colpali_pages 補 event_key / source_key / published_year /
--            published_month / published_yyyymm 屬性
-- Date:      2026-06-18
-- Author:    Jenny
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     polaris-desk-team.polaris_core.colpali_pages（ALTER + UPDATE，5701 列）
--
-- 背景：colpali_pages 現存資料皆為法說會（earnings call）簡報頁，來源皆為公司
--   IR 官網。本表目前只有 published_at（DATE），缺乏 event/source 維度標籤與
--   可直接 GROUP BY 的年/月欄位，補上後可與 R6 ontology event/source 字典對齊，
--   並讓報表依年月彙整不必每次 EXTRACT。
--
-- ⚠️ 套用者請知悉：
--   1. ADD COLUMN IF NOT EXISTS 為冪等操作，重複套用安全。
--   2. UPDATE 全表回填為冪等操作（同樣輸入產生同樣輸出），重複套用安全。
--   3. event_key / source_key 此處皆為常數回填，因現存資料來源單一
--      （法說會簡報、公司 IR 官網）；未來若新增其他來源/事件類型的頁面，
--      寫入流程需自行帶入正確的 event_key / source_key，不可沿用本檔常數。

ALTER TABLE `polaris-desk-team.polaris_core.colpali_pages`
ADD COLUMN IF NOT EXISTS event_key STRING,
ADD COLUMN IF NOT EXISTS source_key STRING,
ADD COLUMN IF NOT EXISTS published_year INT64,
ADD COLUMN IF NOT EXISTS published_month INT64,
ADD COLUMN IF NOT EXISTS published_yyyymm INT64;

UPDATE `polaris-desk-team.polaris_core.colpali_pages`
SET
  event_key = 'earnings_call',
  source_key = 'PRIMARY_COMPANY_IR',
  published_year = EXTRACT(YEAR FROM published_at),
  published_month = EXTRACT(MONTH FROM published_at),
  published_yyyymm = CAST(FORMAT_DATE('%Y%m', published_at) AS INT64)
WHERE TRUE;

-- ── 套用後驗證（預期 5701，且新欄位皆無 NULL）─────────────────────────────
-- SELECT COUNT(*) AS n,
--        COUNTIF(event_key IS NULL) AS null_event_key,
--        COUNTIF(source_key IS NULL) AS null_source_key,
--        COUNTIF(published_year IS NULL) AS null_year,
--        COUNTIF(published_month IS NULL) AS null_month,
--        COUNTIF(published_yyyymm IS NULL) AS null_yyyymm
-- FROM `polaris-desk-team.polaris_core.colpali_pages`;
-- 抽樣核對年月組合是否一致：
-- SELECT published_at, published_year, published_month, published_yyyymm
-- FROM `polaris-desk-team.polaris_core.colpali_pages`
-- LIMIT 10;
