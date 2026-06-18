-- Migration: 建立 polaris_core.r6_* ontology 維度表（R6 Ontology_V1 落地 canonical）
-- Date:      2026-06-18
-- Author:    Wayne（內容 owner：R6；schema 審查：R2；核准：R1；套用：R4 或 R1）
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     polaris-desk-team.polaris_core 新建 12 張 r6_* 維度表 + 載入 seed CSV
--
-- 背景（跨角色決議，2026-06-18）：
--   R4 提出、R2 執行——把 R6 的新 ontology（docs/r6/ontology/Ontology_V1.xlsx）
--   落地進 canonical `polaris_core`，R6 再於 polaris_core 之上建 semantic layer
--   （見 migrations/2026-06-18_create_r6_semantic_layer.sql）。本檔處理「加 ontology」。
--   ⚠️ R2／R6 在 polaris_core 為 READER，無法直接寫；本 migration 仍走 §7 PR，
--      由 R4 或 R1（WRITER）以 BQ_ALLOW_CORE_WRITE=1 套用。內容/schema 由 R2／R6 author。
--
-- 修訂（2026-06-18, PR #104 對齊）：原始 seed 由 #104 前的 xlsx 匯出，遺漏
--   04_disclosure_events 的兩層 taxonomy（event_key／event_type／event_subtype +
--   major_news.* 子分類）與 10_news_source_whitelist 的 SECONDARY_YAHOO／
--   SECONDARY_NEWS_MEDIA。已用 scripts/gen_ontology_seeds.py 由 #104 後 xlsx 重生
--   disclosure_event.csv（新 schema, 10 列）與 news_source_whitelist.csv（15 列），
--   並同步更新下方 r6_disclosure_event DDL。套用前請確認 seed 為最新。
--
-- 來源（單一事實來源）：docs/r6/ontology/seeds/*.csv，由 Ontology_V1.xlsx 對應分頁匯出。
--   sheet → seed → table 對照：
--     01_industry            → industry.csv             → r6_industry
--     03_financial_metric    → financial_metric.csv     → r6_financial_metric
--     04_disclosure_events   → disclosure_event.csv     → r6_disclosure_event
--     05_compliance_terms    → compliance_term.csv      → r6_compliance_term
--     06_theme               → theme.csv                → r6_theme
--     07_risk_signal         → risk_signal.csv          → r6_risk_signal
--     08_company_theme_map   → company_theme_map.csv     → r6_company_theme_map
--     09_company_industry_map→ company_industry_map.csv  → r6_company_industry_map
--     10_news_source_whitelist→ news_source_whitelist.csv→ r6_news_source_whitelist
--     12_source_taxonomy_map → source_taxonomy_map.csv   → r6_source_taxonomy_map
--     14_revenue_metrics_ext → revenue_field.csv         → r6_revenue_field
--     16_quarter_table       → quarter.csv               → r6_quarter
--   未納入（純治理/中繼分頁，R6 內部用，不進 canonical）：
--     00_readme, 02_company（已由 company_dim 覆蓋）, 11_quality_checks,
--     12_governance_decisions, 13_traceability_matrix, 15_revenue_field_matrix,
--     99_change_log。
--   Join key：ticker（治理決議 V1_1_JOIN_KEY_TICKER, 2026-06-09）；company_id 僅參考。
--
-- ⚠️ 套用者請知悉：
--   1. 對 canonical 共用庫的寫入（建表 + 載入），走 §7 PR。
--   2. 重跑安全：DDL 用 CREATE OR REPLACE；bq load 用 --replace（先 truncate 再載）。
--   3. ontology 異動時，請重生對應 seed CSV 並更新本 migration（勿手改單列）。

-- ════════════════════════════════════════════════════════════════════════════
-- 1) DDL —— 建表（schema 與 seed CSV 欄位一致；空字串於 load 時轉 NULL）
-- ════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_industry` (
  industry_id        STRING NOT NULL,
  industry_name      STRING,
  parent_industry_id STRING,       -- 階層父節點（NULL=第一層）
  industry_level     INT64,
  gics_sector_hint   STRING,
  description        STRING,
  keywords           STRING        -- 逗號分隔
)
CLUSTER BY industry_id
OPTIONS(description='R6 Ontology_V1 01_industry 產業分類階層（FR-074~076 多產業基底）。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_financial_metric` (
  metric_id            STRING NOT NULL,  -- join financial_metrics.metric_id
  metric_name          STRING,
  alias                STRING,
  category             STRING,
  unit                 STRING,
  formula_or_definition STRING,
  source_grain         STRING,
  frequency            STRING,
  zero_tolerance       STRING,           -- Y/N：是否零容錯金融數字
  r6_note              STRING,
  standard_code        STRING
)
CLUSTER BY metric_id
OPTIONS(description='R6 Ontology_V1 03_financial_metric 財務指標定義（join key=metric_id）。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_disclosure_event` (
  event_key          STRING NOT NULL,  -- PK：event_type 或 event_type.event_subtype
  event_type         STRING,           -- 第一層：earnings_call / monthly_revenue / news / major_news
  event_type_name    STRING,
  event_subtype      STRING,           -- 第二層：major_news.* 子分類（第一層列為空）
  event_subtype_name STRING,
  category           STRING,
  source_system      STRING,
  required_fields    STRING,
  severity           STRING,
  demo_relevance     STRING,
  r6_notes           STRING
)
CLUSTER BY event_key
OPTIONS(description='R6 Ontology_V1 04_disclosure_events 揭露事件類型（event_key PK／event_type 第一層／event_subtype 第二層，含 major_news.* 子分類；PR #104）。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_compliance_term` (
  category          STRING,
  term_id           STRING NOT NULL,
  term_name         STRING,
  legal_basis       STRING,
  risk_pattern      STRING,
  forbidden_output  STRING,
  safe_response_rule STRING,
  owner             STRING
)
CLUSTER BY term_id
OPTIONS(description='R6 Ontology_V1 05_compliance_terms 法遵名詞（含 NFR-031 紅線）。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_theme` (
  theme_id       STRING NOT NULL,
  theme_name     STRING,
  theme_category STRING,
  description    STRING
)
CLUSTER BY theme_id
OPTIONS(description='R6 Ontology_V1 06_theme 投資主題字典。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_risk_signal` (
  risk_id           STRING NOT NULL,
  risk_name         STRING,
  risk_category     STRING,
  severity          STRING,
  description       STRING,
  related_metric_id STRING,   -- 對映 r6_financial_metric.metric_id
  related_event_id  STRING    -- 對映 r6_disclosure_event.event_key
)
CLUSTER BY risk_id
OPTIONS(description='R6 Ontology_V1 07_risk_signal 風險訊號字典。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_company_theme_map` (
  ticker       STRING NOT NULL,  -- join key
  company_id   STRING,
  company_name STRING,
  theme_id     STRING,           -- 對映 r6_theme.theme_id
  theme_name   STRING,
  priority     STRING,
  source_rank  INT64,
  source_sheet STRING
)
CLUSTER BY ticker
OPTIONS(description='R6 Ontology_V1 08_company_theme_mapping 公司↔主題（多對多）。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_company_industry_map` (
  ticker        STRING NOT NULL,  -- join key
  company_id    STRING,
  company_name  STRING,
  industry_id   STRING,           -- 對映 r6_industry.industry_id
  industry_name STRING,
  mapping_type  STRING,           -- primary / secondary …（多產業 FR-074~076）
  primary_rank  INT64,
  revenue_pct   FLOAT64,          -- 營收占比（目前多為 NULL，待補）
  review_status STRING,
  priority      STRING,
  source_note   STRING,
  source_rank   INT64
)
CLUSTER BY ticker
OPTIONS(description='R6 Ontology_V1 09_company_industry_mapping 公司↔產業（多產業，FR-074~076）。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_news_source_whitelist` (
  source_key        STRING NOT NULL,
  source_name       STRING,
  trust_tier        STRING,   -- Primary / Secondary …
  source_type       STRING,
  use_case          STRING,
  allowed_for_fact  STRING,   -- Y/N
  r6_note           STRING,
  citation_required STRING    -- Y/N
)
CLUSTER BY source_key
OPTIONS(description='R6 Ontology_V1 10_news_source_whitelist 新聞來源白名單與可信度分級。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_source_taxonomy_map` (
  canonical_source_enum          STRING NOT NULL,
  ontology_source_type           STRING,
  annotation_source_type_allowed STRING,
  question_bank_source_type      STRING,
  ground_truth_source_prefix     STRING,
  citation_required_default      STRING,  -- Y/N
  description                    STRING
)
CLUSTER BY canonical_source_enum
OPTIONS(description='R6 Ontology_V1 12_source_taxonomy_mapping 跨產物 source 列舉對照。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_revenue_field` (
  field_name       STRING NOT NULL,
  display_name_zh  STRING,
  data_type        STRING,
  currency         STRING,
  unit             STRING,
  description      STRING,
  source           STRING,
  source_enum      STRING,
  nullable         STRING,   -- Y/N（欄位語意層級，非 BQ 約束）
  example_value    STRING,
  calculation_rule STRING,
  field_class      STRING,   -- Stored Fact / Derived …
  governance_owner STRING
)
CLUSTER BY field_name
OPTIONS(description='R6 Ontology_V1 14_revenue_metrics_extension 月營收衍生欄位定義。');

CREATE OR REPLACE TABLE `polaris-desk-team.polaris_core.r6_quarter` (
  fiscal_period       STRING NOT NULL,  -- 對映 financial_metrics.fiscal_period（如 2024Q1）
  year                INT64,
  quarter             INT64,
  yyyyqq              STRING,
  quarter_start_month INT64,
  quarter_end_month   INT64,
  start_date          DATE,
  end_date            DATE,
  month_keys          STRING,           -- 逗號分隔月份 key（如 202401,202402,202403）
  r6_notes            STRING
)
CLUSTER BY fiscal_period
OPTIONS(description='R6 Ontology_V1 16_quarter_table 季別↔月份/日期對齊維度。');

-- ════════════════════════════════════════════════════════════════════════════
-- 2) 載入 —— 套用者在 shell 執行（從 repo 根目錄；--replace 可重跑）
--    前置：export BQ_ALLOW_CORE_WRITE=1；帳號需 polaris_core dataset WRITER。
-- ════════════════════════════════════════════════════════════════════════════
--
--   DS=polaris-desk-team:polaris_core
--   SEEDS=docs/r6/ontology/seeds
--   load() { bq load --replace --source_format=CSV --skip_leading_rows=1 \
--              --allow_quoted_newlines "$DS.$1" "$SEEDS/$2"; }
--
--   load r6_industry                industry.csv
--   load r6_financial_metric        financial_metric.csv
--   load r6_disclosure_event        disclosure_event.csv
--   load r6_compliance_term         compliance_term.csv
--   load r6_theme                   theme.csv
--   load r6_risk_signal             risk_signal.csv
--   load r6_company_theme_map       company_theme_map.csv
--   load r6_company_industry_map    company_industry_map.csv
--   load r6_news_source_whitelist   news_source_whitelist.csv
--   load r6_source_taxonomy_map     source_taxonomy_map.csv
--   load r6_revenue_field           revenue_field.csv
--   load r6_quarter                 quarter.csv
--
-- 註：表已以上方 DDL 建好 schema，bq load 沿用該 schema（不 autodetect）；
--     CSV 空字串於載入時轉為 NULL（nullable 欄位）。

-- ════════════════════════════════════════════════════════════════════════════
-- 3) 套用後驗證（預期列數 = seed CSV 列數）
-- ════════════════════════════════════════════════════════════════════════════
-- SELECT 'r6_industry' t, COUNT(*) n FROM `polaris-desk-team.polaris_core.r6_industry`
-- UNION ALL SELECT 'r6_financial_metric',     COUNT(*) FROM `polaris-desk-team.polaris_core.r6_financial_metric`
-- UNION ALL SELECT 'r6_disclosure_event',     COUNT(*) FROM `polaris-desk-team.polaris_core.r6_disclosure_event`
-- UNION ALL SELECT 'r6_compliance_term',      COUNT(*) FROM `polaris-desk-team.polaris_core.r6_compliance_term`
-- UNION ALL SELECT 'r6_theme',                COUNT(*) FROM `polaris-desk-team.polaris_core.r6_theme`
-- UNION ALL SELECT 'r6_risk_signal',          COUNT(*) FROM `polaris-desk-team.polaris_core.r6_risk_signal`
-- UNION ALL SELECT 'r6_company_theme_map',    COUNT(*) FROM `polaris-desk-team.polaris_core.r6_company_theme_map`
-- UNION ALL SELECT 'r6_company_industry_map', COUNT(*) FROM `polaris-desk-team.polaris_core.r6_company_industry_map`
-- UNION ALL SELECT 'r6_news_source_whitelist',COUNT(*) FROM `polaris-desk-team.polaris_core.r6_news_source_whitelist`
-- UNION ALL SELECT 'r6_source_taxonomy_map',  COUNT(*) FROM `polaris-desk-team.polaris_core.r6_source_taxonomy_map`
-- UNION ALL SELECT 'r6_revenue_field',        COUNT(*) FROM `polaris-desk-team.polaris_core.r6_revenue_field`
-- UNION ALL SELECT 'r6_quarter',              COUNT(*) FROM `polaris-desk-team.polaris_core.r6_quarter`;
-- 預期：industry=18, financial_metric=22, disclosure_event=10, compliance_term=38,
--       theme=17, risk_signal=22, company_theme_map=55, company_industry_map=27,
--       news_source_whitelist=15, source_taxonomy_map=14, revenue_field=6, quarter=12。
--
-- 接地檢查（mapping 的 ticker 必須全部存在於 company_dim）：
-- SELECT DISTINCT m.ticker
-- FROM `polaris-desk-team.polaris_core.r6_company_industry_map` m
-- LEFT JOIN `polaris-desk-team.polaris_core.company_dim` d USING (ticker)
-- WHERE d.ticker IS NULL;   -- 預期空集合
