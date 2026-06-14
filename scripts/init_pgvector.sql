-- 本地 Postgres 初始化：啟用 pgvector extension
-- docker compose 第一次起 db 時自動執行
CREATE EXTENSION IF NOT EXISTS vector;

-- 範例 schema（@R4 W1 依 PRD §18 Data Model 調整）
-- 768 維對應 gemini-embedding-2 的 output_dimensionality（見 .env EMBEDDING_DIM）
CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    company     TEXT,
    period      TEXT,                 -- 供 Temporal Anchoring 用（如 2024Q3）
    content     TEXT NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB DEFAULT '{}'::jsonb,
    owner       TEXT DEFAULT NULL,          -- principal who owns this doc (NULL = public)
    confidential BOOLEAN NOT NULL DEFAULT FALSE  -- MNPI / restricted flag
);

-- 向量近似搜尋索引（cosine）
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- ⚠️ 效能三條雷（R4 必看）：pgvector 在本專案規模（約 1–3 萬向量）查詢只要幾 ms，
--    「慢」幾乎都是設定錯，不是 pgvector 不行：
--   1) 索引建在 cosine（vector_cosine_ops）→ 查詢「必須」用 <=> 運算子；
--      用錯 <->（L2）或 <#>（內積）不會走索引，會退化成全表掃描。
--   2) 查詢要寫成  ORDER BY embedding <=> $query LIMIT k  才吃得到索引；
--      用 EXPLAIN ANALYZE 確認是 "Index Scan using idx_chunks_embedding"，不是 "Seq Scan"。
--   3) 帶 company/period 過濾、候選太少時，開
--        SET hnsw.iterative_scan = relaxed_order;   或   SET hnsw.ef_search = 100;
--      （此規模調高幾乎不花時間，可提升 recall）。
-- 上雲（W4 / Q-03）改用 BigQuery VECTOR_SEARCH 時：維度固定 768、距離一樣用 cosine，
-- 並用同一份 eval 驗證分數沒掉（後端切換見 .env 的 VECTOR_BACKEND）。

CREATE INDEX IF NOT EXISTS idx_chunks_company ON chunks (company);
CREATE INDEX IF NOT EXISTS idx_chunks_period  ON chunks (period);
CREATE INDEX IF NOT EXISTS idx_chunks_owner   ON chunks (owner);
