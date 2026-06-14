-- Migration: add owner + confidential columns for access-control (issue #32)
-- Date:      2026-06-14
-- Author:    Wayne
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     BigQuery: polaris_core.chunks
--
-- 背景：R4 access-control（issue #32）需要 owner / confidential 欄，
--       BigQueryStore.search() 的 viewer filter 才能在 WHERE 子句生效。
-- ⚠️  ADD COLUMN IF NOT EXISTS 為冪等操作，重複套用安全。

-- BigQuery: polaris_core.chunks
ALTER TABLE `polaris-desk-team.polaris_core.chunks`
ADD COLUMN IF NOT EXISTS owner STRING,
ADD COLUMN IF NOT EXISTS confidential BOOL DEFAULT FALSE;
