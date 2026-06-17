-- Migration: 建立 polaris_core.company_dim（ticker → 公司名 維度表）
-- Date:      2026-06-17
-- Author:    Wayne
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     polaris-desk-team.polaris_core.company_dim（新建 + 載入 20 列）
--
-- 背景：polaris_core 各事實表（chunks / financial_metrics / events）只存 ticker，
--   無公司名欄。本維度表把 R6 ontology（docs/r6/ontology/Ontology_V1.xlsx
--   `02_company公司`）的 canonical 公司清單落地為可被 BQ JOIN 的維度，讓
--   RAG metadata / 報表不必 hardcode ticker→name 對照。
--
-- 來源：docs/r6/ontology/seeds/company_dim.csv（由 ontology 02_company 產生，
--   單一事實來源；本檔 INSERT 內容與該 CSV 一致）。
-- Join key：ticker（治理決議 V1_1_JOIN_KEY_TICKER，2026-06-09）。company_id
--   僅作參考/治理用途。
--
-- ⚠️ 套用者請知悉：
--   1. 這是對 canonical 共用庫的寫入（建表 + 載入），走 §7 PR。
--   2. 重跑安全：使用 CREATE OR REPLACE，會以 ontology 內容覆寫整表。
--   3. ontology 公司清單異動時，請重生 CSV 並更新本 migration（勿手改單列）。

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.company_dim` (
  ticker        STRING NOT NULL,  -- join key（對映 chunks/financial_metrics/events.ticker）
  company_name  STRING,           -- canonical 中文顯示名
  english_name  STRING,
  market        STRING,           -- 上市 / 上櫃 …
  industry_id   STRING,           -- 主產業（對映 09_company_industry_mapping primary）
  industry_name STRING,
  is_financial  BOOL,             -- 金融業旗標
  aliases       STRING,           -- 逗號分隔別名（含舊簡稱 / 英文 / 代號）
  company_id    STRING            -- 參考用（治理），非 join key
)
CLUSTER BY ticker
OPTIONS(description='Canonical ticker→company dimension, sourced from R6 Ontology_V1 02_company. Join key=ticker (V1_1_JOIN_KEY_TICKER, 2026-06-09).');

INSERT INTO `polaris-desk-team.polaris_core.company_dim`
  (ticker, company_name, english_name, market, industry_id, industry_name, is_financial, aliases, company_id)
VALUES
  ('1216', '統一', 'Uni-President Enterprises', '上市', 'IND_FOOD', '食品', FALSE, '統一,Uni-President,1216', '73251209'),
  ('2303', '聯電', 'United Microelectronics', '上市', 'IND_FOUNDRY', '晶圓代工', FALSE, '聯電,UMC,2303', '47217677'),
  ('2308', '台達電', 'Delta Electronics', '上市', 'IND_AI_INFRA', 'AI基礎設施', FALSE, '台達電,Delta,2308', '34051920'),
  ('2317', '鴻海', 'Hon Hai Precision Industry', '上市', 'IND_EMS', '電子代工', FALSE, '鴻海,Hon Hai,2317', '04541302'),
  ('2330', '台積電', 'Taiwan Semiconductor Manufacturing Company', '上市', 'IND_FOUNDRY', '晶圓代工', FALSE, '台積電,TSMC,2330', '22099131'),
  ('2357', '華碩', 'ASUSTeK Computer', '上市', 'IND_COMPUTER_BRAND', '電腦品牌', FALSE, '華碩,ASUS,2357', '23638777'),
  ('2382', '廣達', 'Quanta Computer', '上市', 'IND_AI_SERVER', 'AI伺服器', FALSE, '廣達,Quanta,2382', '22822281'),
  ('2412', '中華電', 'Chunghwa Telecom', '上市', 'IND_TELECOM', '電信', FALSE, '中華電信,Chunghwa Telecom,2412', '96979933'),
  ('2454', '聯發科', 'MediaTek', '上市', 'IND_IC_DESIGN', 'IC設計', FALSE, '聯發科,MediaTek,2454', '84149961'),
  ('2881', '富邦金', 'Fubon Financial Holding', '上市', 'IND_FINANCIAL_HOLDING', '金融控股', TRUE, '富邦金,Fubon,2881', '03374805'),
  ('2882', '國泰金', 'Cathay Financial Holding', '上市', 'IND_FINANCIAL_HOLDING', '金融控股', TRUE, '國泰金,Cathay FHC,2882', '70827406'),
  ('2884', '玉山金', 'E.SUN Financial Holding', '上市', 'IND_FINANCIAL_HOLDING', '金融控股', TRUE, '玉山金,E.SUN FHC,2884', '70796305'),
  ('2886', '兆豐金', 'Mega Financial Holding', '上市', 'IND_FINANCIAL_HOLDING', '金融控股', TRUE, '兆豐金,Mega FHC,2886', '70796754'),
  ('2891', '中信金', 'CTBC Financial Holding', '上市', 'IND_FINANCIAL_HOLDING', '金融控股', TRUE, '中信金,CTBC,2891', '80333992'),
  ('2892', '第一金', 'First Financial Holding', '上市', 'IND_FINANCIAL_HOLDING', '金融控股', TRUE, '第一金,First FHC,2892', '80351999'),
  ('3034', '聯詠', 'Novatek Microelectronics', '上市', 'IND_IC_DESIGN', 'IC設計', FALSE, '聯詠,Novatek,3034', '84149955'),
  ('3037', '欣興', 'Unimicron Technology', '上市', 'IND_ABF_SUBSTRATE', 'ABF載板', FALSE, '欣興,Unimicron,3037', '23535435'),
  ('3231', '緯創', 'Wistron', '上市', 'IND_AI_SERVER', 'AI伺服器', FALSE, '緯創,Wistron,3231', '12868358'),
  ('3711', '日月光投控', 'ASE Technology Holding', '上市', 'IND_OSAT', '半導體封測', FALSE, '日月光投控,ASEH,3711', '29187308'),
  ('6669', '緯穎', 'Wiwynn', '上市', 'IND_AI_SERVER', 'AI伺服器', FALSE, '緯穎,Wiwynn,6669', '53687704');

-- ── 套用後驗證（預期 20，且與事實表 ticker 一致）──────────────────────────
-- SELECT COUNT(*) AS n FROM `polaris-desk-team.polaris_core.company_dim`;          -- 預期 20
-- 維度涵蓋事實表所有 ticker（移除 2324 後應為空集合）：
-- SELECT DISTINCT c.ticker
-- FROM `polaris-desk-team.polaris_core.chunks` c
-- LEFT JOIN `polaris-desk-team.polaris_core.company_dim` d USING (ticker)
-- WHERE d.ticker IS NULL;
