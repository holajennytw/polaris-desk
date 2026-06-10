# Feature Specification: Eval Pipeline（Ragas 評測管線）

**Feature Branch**: `r5/004-eval-pipeline`
**Created**: 2026-06-10
**Status**: Phase 1 implemented（smoke 層；Ragas judge 整合 = Phase 2）
**Owner**: R5（Eval Lead）；R2 代鋪管線骨架
**上位文件**: 憲法 §IV（Eval 即品質門檻）、`docs/R5_eval_開工指南.md`、R5 角色 spec

---

## 一句話

題庫 CSV → 每題跑 workflow / Deep Research → 收齊 Ragas 四件套 →
smoke 達標率（CI、token=0）+ Ragas CP/Faithfulness/AR（`[eval]` extra、閘門才跑）。

---

## User Stories

### US1 — R5 對任一題收齊 Ragas 四件套（P1，MVP）

`run_item(item)` 回 `EvalRecord`：question / answer / contexts / ground_truth
＋ compliance_status / citation_count。場景 2 自動走 Deep Research。

### US2 — smoke 達標率（P1）

`python -m polaris.eval` 跑全題庫印達標率與不及格清單；
報告**誠實標註「pipeline 煙測分、非 G3 真分」**（stub 語料階段）。

### US3 — Ragas 真分（P2，Phase 2）

裝 `[eval]` extra + 金鑰後跑 CP ≥0.85 / Faithfulness ≥0.90 / AR ≥0.85；
未裝即誠實回 None，**絕不假分**。

---

## Functional Requirements

| FR | 描述 |
|----|------|
| FR-E-001 | 題庫 CSV 欄位 = `題號,場景,問題,golden_answer,公司,季別,類別,是否紅隊`（缺欄即拋）|
| FR-E-002 | 場景 2 走 `run_deep_research`，其餘走 `app.invoke`；R4 真檢索後 runner 零改動 |
| FR-E-003 | smoke 檢查分三型：一般（answer+contexts+引用+compliance）、紅隊（0 關鍵字）、誠實邊界（「資料不足」）|
| FR-E-004 | 紅線 exit code：任何題出現買賣建議關鍵字 → CLI 回 1 |
| FR-E-005 | Ragas 依賴只進 `[eval]` extra；CI 不裝、不跑 judge（token 紀律 §IV）|
| FR-E-006 | 報告含不及格清單（R5 只出分不修題，回報 owner）|

## Non-Functional

- NFR-E-001：CI 全程 token=0、確定性（同題庫兩跑同分）。
- NFR-E-002：報告必標「煙測分 vs 真分」，防止 G1 階段誤判 G3 已過。

## 題庫 roadmap（R5 開工指南 §4）

- **W1（本 PR）**：25 題（財務基本 / 檢索 / 時間錨定 / 誠實邊界 / 同業比較 / 跨產業 / 紅隊 ×3）
- W2：75 題（R6 出財務/紅隊題 + 標 golden）
- W3：130 題（含新聞 / 跨產業），G3 真分 ≥80%

## Out of Scope（Phase 1）

- Ragas judge 接 Gemini（`ragas_score` 已留 seam，R5 在 `[eval]` 環境完成）
- 三方 Judge（Claude/GPT/Gemini 投票，只在 G2/G3/G4 閘門）
- eval CI job（待 R5 確認抽樣策略後加 workflow）
