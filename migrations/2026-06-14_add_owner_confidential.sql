-- Migration: add owner + confidential columns for access-control (issue #32)
-- Date:      2026-06-14
-- Author:    Wayne
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 套用）
-- Scope:     pgvector fallback：本地 Postgres chunks 表
--
-- 背景：R4 access-control（issue #32）需要 owner / confidential 欄，
--       HybridRetriever 的 viewer filter 才能在 WHERE 子句生效。
-- ⚠️  pgvector 已建立的 DB 需套用本 migration；新 DB 用 init_pgvector.sql 即可。

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS owner TEXT DEFAULT NULL;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS confidential BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_chunks_owner ON chunks (owner);
