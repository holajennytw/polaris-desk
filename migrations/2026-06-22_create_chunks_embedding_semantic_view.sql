-- Migration: 建立 polaris_core.v_chunks_embedding_semantic
--            （polaris_core.chunks LEFT JOIN polaris_core.v_chunk_semantic
--            ON chunk_id，補回 v_chunk_semantic 刻意排除的 embedding，
--            供需要「向量 + 語意 metadata」一次取得的場景使用）
-- Date:      2026-06-22
-- Author:    Jenny
-- SOP:       CREATE OR REPLACE VIEW，不改動 chunks / v_chunk_semantic 本體，
--            無需 ALTER/UPDATE polaris_core 既有資料，可重跑、可直接
--            DROP VIEW 回退。走 docs/協作開發環境_SOP_v1.md §7（R2 審查 /
--            R1 核准 / R4 或 R1 套用，套用端需 BQ_ALLOW_CORE_WRITE=1 +
--            dataset WRITER）。
-- Scope:     polaris-desk-team.polaris_core.v_chunks_embedding_semantic（新建 view）
-- 依賴：     polaris_core.v_chunk_semantic 已由
--            migrations/2026-06-18_chunks_add_event_source_published_attrs_semantic.sql
--            建好（唯讀 join，不動該檔）。
--
-- 背景：v_chunk_semantic 刻意排除 chunks.embedding 大欄位（供 RAG 引用
--   metadata 顯示用，避免每次都拖一份向量）。但向量檢索後續若要直接帶出
--   event_key / source_key / published_year 等語意欄位做篩選或彙整，需要
--   把 embedding 跟這些欄位接在一起查，本 view 即補這個用途：以
--   chunks.chunk_id 為準 LEFT JOIN v_chunk_semantic，一次拿到向量＋語意
--   metadata。
--
-- ⚠️ 套用者請知悉：
--   1. CREATE OR REPLACE VIEW 為冪等操作，重複套用安全。
--   2. 本 view 含 embedding（ARRAY<FLOAT64>），查詢成本較高，僅在需要向量
--      時使用；純看 metadata 請改用 v_chunk_semantic。

CREATE OR REPLACE VIEW `polaris-desk-team.polaris_core.v_chunks_embedding_semantic`
OPTIONS(description='chunks 向量 + v_chunk_semantic 語意 metadata 一次取得，供向量檢索後續篩選/彙整用。')
AS
SELECT
  ch.chunk_id,
  ch.embedding,
  s.ticker,
  s.company_name,
  s.industry_name,
  s.doc_type,
  s.fiscal_period,
  s.year,
  s.quarter,
  s.published_at,
  s.published_year,
  s.published_month,
  s.published_yyyymm,
  s.chunk_text,
  s.event_key,
  s.event_type,
  s.event_type_name,
  s.event_subtype,
  s.event_subtype_name,
  s.event_category,
  s.event_severity,
  s.source_key,
  s.source_name,
  s.trust_tier,
  s.allowed_for_fact,
  s.citation_required
FROM `polaris-desk-team.polaris_core.chunks` ch
LEFT JOIN `polaris-desk-team.polaris_core.v_chunk_semantic` s USING (chunk_id);

-- ── 套用後驗證（預期列數與 chunks 本表一致，且不放大）───────────────────────
-- SELECT
--   (SELECT COUNT(*) FROM `polaris-desk-team.polaris_core.chunks`) AS n_chunks,
--   (SELECT COUNT(*) FROM `polaris-desk-team.polaris_core.v_chunks_embedding_semantic`) AS n_view;
-- 接地：LEFT JOIN 對 chunk_id（唯一鍵），不應放大列數；若放大代表
-- v_chunk_semantic 有重複 chunk_id。
