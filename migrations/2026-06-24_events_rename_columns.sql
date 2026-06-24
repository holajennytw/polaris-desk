-- Migration: polaris_core.events 欄位更名
--            event_type  → event_key
--            source_name → source_key
-- Date:      2026-06-24
-- Author:    R6（WayneSHC）
-- SOP:       docs/協作開發環境_SOP_v1.md §7
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + polaris_core WRITER。
-- Scope:     polaris-desk-team.polaris_core.events（ALTER COLUMN — 僅改欄名，不動資料）
--
-- 背景：R6 Ontology_V1 以 event_key（raw code）/ event_type（顯示名）區分兩層語意；
--       原 events 表沿用舊名 event_type（實為 raw code），造成與 r6_disclosure_event、
--       v_chunk_semantic 的命名不一致。同理 source_name 改為 source_key 對齊
--       r6_news_source_whitelist.source_key。
--
-- 套用狀態：✅ 已由 R6 直接套用至 live polaris_core（2026-06-24）。
--           本檔為事後補錄，目的是保留 audit trail，勿重複套用。
--
-- 後端同步：
--   src/polaris/structured_store.py  list_events() SQL 改用 event_key / source_key
--   src/polaris/api.py               EventResponse model event_type → event_key，新增 source_key
-- 前端同步：
--   frontend/src/types/api.ts        EventRaw / ResearchCitationRaw 已使用 event_key / source_key
--   frontend/src/lib/adapters.ts     citationLabel() 已使用 event_key / source_key
-- 文件同步：
--   docs/frontend/資料表欄位表.md     §3 events 表欄位更新（2026-06-24）
--
-- ⚠️ 本檔已套用，請勿重複執行。BigQuery ALTER COLUMN RENAME 為 DDL，冪等性未保證。

-- ── Step 1：event_type → event_key ────────────────────────────────────────
ALTER TABLE `polaris-desk-team.polaris_core.events`
RENAME COLUMN event_type TO event_key;

-- ── Step 2：source_name → source_key ─────────────────────────────────────
ALTER TABLE `polaris-desk-team.polaris_core.events`
RENAME COLUMN source_name TO source_key;

-- ── 套用後驗證 ────────────────────────────────────────────────────────────
-- SELECT event_id, ticker, event_key, source_key
-- FROM `polaris-desk-team.polaris_core.events`
-- LIMIT 5;
-- 預期：event_key 有值（major_news/monthly_revenue/earnings_call/news）；
--       source_key 部分有值（NULL 合理，並非所有事件都有來源代碼）。
