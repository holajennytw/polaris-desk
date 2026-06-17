-- Migration: 從 polaris_core 移除 ticker=2324（仁寶）孤兒資料
-- Date:      2026-06-17
-- Author:    Wayne
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     polaris-desk-team.polaris_core.chunks（DELETE 79 列）
--
-- 背景：2324（仁寶）不在 R6 ontology（docs/r6/ontology/Ontology_V1.xlsx
--   `02_company公司` 的 20 家 canonical 清單）內，屬孤兒 ticker。盤點結果：
--     - chunks                : 79 列（doc_type=presentation，2024-03-01 ~ 2025-08-12）
--     - financial_metrics     : 0 列
--     - events                : 0 列
--     - chunks_pending_reembed: 0 列
--     - colpali_pages         : 0 列（無 ticker 欄）
--   故僅 chunks 含 2324，無對應財報/事件，無法被 ontology 的 ticker join key
--   接地，決議移除以維持 canonical 與 ontology 一致。
--
-- ⚠️ 套用者請知悉：
--   1. 這是對 canonical 共用庫的破壞性 DELETE，不可逆。套用前請確認已有
--      polaris_core 備份/快照（或先 SELECT 出 79 列另存）。
--   2. 預期刪除列數 = 79。若 ROW COUNT 不符，請中止並回報（代表上游又有
--      2324 寫入）。

-- ── 0. 套用前快照（建議；保留被刪資料供稽核/回溯）──────────────────────────
-- CREATE TABLE `polaris-desk-team.polaris_core._archive_2324_chunks_20260617` AS
-- SELECT * FROM `polaris-desk-team.polaris_core.chunks` WHERE ticker = '2324';

-- ── 1. 套用前檢查（預期 79）──────────────────────────────────────────────
-- SELECT COUNT(*) AS rows_to_delete
-- FROM `polaris-desk-team.polaris_core.chunks`
-- WHERE ticker = '2324';

-- ── 2. DELETE ────────────────────────────────────────────────────────────
DELETE FROM `polaris-desk-team.polaris_core.chunks`
WHERE ticker = '2324';

-- ── 3. 套用後驗證（預期 0）──────────────────────────────────────────────
-- SELECT COUNT(*) AS remaining_2324
-- FROM `polaris-desk-team.polaris_core.chunks`
-- WHERE ticker = '2324';
--
-- 並重跑 ticker 對帳，確認 chunks 的 distinct ticker 與 ontology 20 家一致：
-- SELECT DISTINCT ticker FROM `polaris-desk-team.polaris_core.chunks` ORDER BY ticker;
