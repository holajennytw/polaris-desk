-- Migration: 新增 4 個指標到 polaris_core.r6_financial_metric（additive MERGE）
-- Date:      2026-06-25
-- Author:    Jenny（內容 owner：R6；schema 審查：R2；核准：R1；套用：R4 或 R1）
-- SOP:       走 docs/協作開發環境_SOP_v1.md §7（R2 審查 / R1 核准 / R4 或 R1 套用，
--            套用端需 BQ_ALLOW_CORE_WRITE=1 + dataset WRITER）
-- Scope:     polaris-desk-team.polaris_core.r6_financial_metric 新增 4 列（不動既有列）
--
-- 背景：
--   docs/r6/ontology/seeds/financial_metric.csv 由 R6 更新，新增 4 個指標：
--     pretax_income      稅前淨利     （獲利；新台幣千元）
--     operating_expense  營業費用     （獲利；新台幣千元）
--     revenue_delta      營收增減金額 （成長；TWD_thousand，需搭配 comparison_base）
--     revenue_yoy        營收年增率   （成長；%，單期年增率，勿與 ytd_yoy 混用）
--   表列數：22 → 26。schema 未變。
--
-- ⚠️ 套用者請知悉：
--   1. 對 canonical 共用庫的寫入，走 §7 PR。
--   2. 重跑安全：以 metric_id 為鍵的 MERGE，僅在不存在時 INSERT（既有列不覆寫）。
--   3. 表 DDL 仍以 migrations/2026-06-18_create_r6_ontology.sql 為準（schema 一致）。
--   4. 與 financial_metric.csv 單一事實來源的關係：本檔僅補這 4 列；若日後做全量
--      重載（bq load --replace ...），seed CSV 仍為權威來源。

-- ════════════════════════════════════════════════════════════════════════════
-- 1) MERGE —— 僅新增不存在的 metric_id（既有 22 列不受影響）
--    前置：export BQ_ALLOW_CORE_WRITE=1；帳號需 polaris_core dataset WRITER。
-- ════════════════════════════════════════════════════════════════════════════

MERGE `polaris-desk-team.polaris_core.r6_financial_metric` T
USING (
  SELECT * FROM UNNEST([
    STRUCT(
      'pretax_income' AS metric_id,
      '稅前淨利' AS metric_name,
      '稅前利益,所得稅前損益,pretax profit' AS alias,
      '獲利' AS category,
      '新台幣千元' AS unit,
      '所得稅前損益，用於觀察公司稅前獲利能力。' AS formula_or_definition,
      '財報/IFRS' AS source_grain,
      '季/年' AS frequency,
      'Y' AS zero_tolerance,
      '不等同於 net_income，需注意是否為稅前數。' AS r6_note,
      'TBD' AS standard_code
    ),
    STRUCT(
      'operating_expense', '營業費用', '營業費用合計,OPEX,operating expenses',
      '獲利', '新台幣千元',
      '營業活動相關費用，通常包含推銷費用、管理費用、研發費用等。',
      '財報/IFRS', '季/年', 'Y',
      '若資料來源拆分 SG&A / R&D，需確認是否加總為營業費用。', 'TBD'
    ),
    STRUCT(
      'revenue_delta', '營收增減金額', '營收增減,營收差額,revenue change',
      '成長', 'TWD_thousand',
      '本期營收與比較基期營收的差額，可用於月營收、季度營收或年度營收比較。',
      '計算指標', '月/季/年', 'Y',
      '需搭配 comparison_base，例如 MoM、YoY、QoQ 或指定比較期間。', 'TBD'
    ),
    STRUCT(
      'revenue_yoy', '營收年增率', '單期營收年增率,revenue YoY',
      '成長', '%',
      '(本期營收 - 去年同期營收) / 去年同期營收',
      '計算指標', '月/季/年', 'Y',
      'revenue_yoy 是單期營收年增率；不要和 ytd_yoy 混用。', 'TBD'
    )
  ])
) S
ON T.metric_id = S.metric_id
WHEN NOT MATCHED THEN
  INSERT (metric_id, metric_name, alias, category, unit, formula_or_definition,
          source_grain, frequency, zero_tolerance, r6_note, standard_code)
  VALUES (S.metric_id, S.metric_name, S.alias, S.category, S.unit, S.formula_or_definition,
          S.source_grain, S.frequency, S.zero_tolerance, S.r6_note, S.standard_code);

-- ════════════════════════════════════════════════════════════════════════════
-- 2) 套用後驗證
-- ════════════════════════════════════════════════════════════════════════════
-- SELECT COUNT(*) n FROM `polaris-desk-team.polaris_core.r6_financial_metric`;
-- -- 預期：n = 26
--
-- 確認新增 4 個指標已載入：
-- SELECT metric_id, metric_name, category, unit
-- FROM `polaris-desk-team.polaris_core.r6_financial_metric`
-- WHERE metric_id IN ('pretax_income','operating_expense','revenue_delta','revenue_yoy')
-- ORDER BY metric_id;   -- 預期 4 列
