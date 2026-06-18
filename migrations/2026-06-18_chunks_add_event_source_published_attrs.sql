-- Migration: chunks 補 event_key / source_key / published_year /
--            published_month / published_yyyymm 屬性
-- Date:      2026-06-18
-- Author:    Jenny
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     polaris-desk-team.polaris_core.chunks（ALTER + UPDATE，6885 列）
--
-- 背景：chunks 現存 doc_type 僅 3 種（major_news 5232 / transcript 1608 /
--   news 45，無 presentation），缺乏 event/source 維度標籤與可直接 GROUP BY
--   的年/月欄位，補上後可與 R6 ontology event/source 字典對齊，並讓報表依
--   年月彙整不必每次 EXTRACT。event_key / source_key 依 doc_type 對映：
--     doc_type    -> event_key          / source_key
--     transcript  -> earnings_call      / PRIMARY_EC_TRANSCRIPT
--     major_news  -> major_news.others  / PRIMARY_MOPS
--     news        -> news               / SECONDARY_NEWS_MEDIA
--
-- ⚠️ 套用者請知悉：
--   1. ADD COLUMN IF NOT EXISTS 為冪等操作，重複套用安全。
--   2. UPDATE 全表回填為冪等操作（同樣輸入產生同樣輸出），重複套用安全。
--   3. event_key / source_key 依現存 doc_type 詞彙做常數對映；若未來新增
--      其他 doc_type，CASE 不會命中，event_key / source_key 會落空（NULL），
--      需先擴充本檔對映表再套用，不可沿用本檔常數覆蓋未知的 doc_type。

ALTER TABLE `polaris-desk-team.polaris_core.chunks`
ADD COLUMN IF NOT EXISTS event_key STRING,
ADD COLUMN IF NOT EXISTS source_key STRING,
ADD COLUMN IF NOT EXISTS published_year INT64,
ADD COLUMN IF NOT EXISTS published_month INT64,
ADD COLUMN IF NOT EXISTS published_yyyymm INT64;

UPDATE `polaris-desk-team.polaris_core.chunks`
SET
  event_key = CASE doc_type
    WHEN 'transcript' THEN 'earnings_call'
    WHEN 'major_news' THEN 'major_news.others'
    WHEN 'news' THEN 'news'
  END,
  source_key = CASE doc_type
    WHEN 'transcript' THEN 'PRIMARY_EC_TRANSCRIPT'
    WHEN 'major_news' THEN 'PRIMARY_MOPS'
    WHEN 'news' THEN 'SECONDARY_NEWS_MEDIA'
  END,
  published_year = EXTRACT(YEAR FROM published_at),
  published_month = EXTRACT(MONTH FROM published_at),
  published_yyyymm = CAST(FORMAT_DATE('%Y%m', published_at) AS INT64)
WHERE TRUE;

-- ── 套用後驗證（預期 6885，且新欄位皆無 NULL）─────────────────────────────
-- SELECT COUNT(*) AS n,
--        COUNTIF(event_key IS NULL) AS null_event_key,
--        COUNTIF(source_key IS NULL) AS null_source_key,
--        COUNTIF(published_year IS NULL) AS null_year,
--        COUNTIF(published_month IS NULL) AS null_month,
--        COUNTIF(published_yyyymm IS NULL) AS null_yyyymm
-- FROM `polaris-desk-team.polaris_core.chunks`;
-- 依 doc_type 抽樣核對對映是否正確：
-- SELECT doc_type, event_key, source_key, COUNT(*) AS n
-- FROM `polaris-desk-team.polaris_core.chunks`
-- GROUP BY doc_type, event_key, source_key;
-- 抽樣核對年月組合是否一致：
-- SELECT published_at, published_year, published_month, published_yyyymm
-- FROM `polaris-desk-team.polaris_core.chunks`
-- LIMIT 10;
