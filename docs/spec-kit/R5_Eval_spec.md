# 角色規格書（Spec Kit）：R5 — AI 品質 · Eval Lead

**Role**: R5 Ragas + 三方 Judge + 130 題 ≥ 80% **色**：紅
**對應**：專題 spec SC-001/002/003；4 週計畫 R5 卡 **Status**: 尚未開工（2026-06-04；開工指南已備、可即刻動）

## 1. Mission
當「考官」：架好 Ragas 自動評分、累積題庫到 130 題、接 CI 每日跑分、導入三方 Judge 投票，W3 把 Eval 衝到 ≥ 80%（G3 硬門檻）。
- **In scope**：Ragas pipeline、題庫 / golden answer、三方 Judge（Claude + GPT + Gemini）、評分 CI、Eval 報告。
- **Out of scope**：修不及格的題（回報給對應角色修）、金融正確性判定（R6 出題 / 標註）。

## 2. Deliverables & Acceptance Criteria

| 交付物 | 對應 | 可驗收標準（measurable）|
|---|---|---|
| Ragas pipeline | G1 | 能對一批題自動跑出 Context Precision / Faithfulness / Answer Relevance 分數 |
| 130 題題庫 | SC-002 | 130 題 + 場景 4 獨立 10 題，**每題附 golden answer** |
| 評分 CI | G2 | 每次 commit 自動跑分；**CI 用 1 個便宜模型（Flash）省成本** |
| 三方 Judge | SC-001 | Claude + GPT + Gemini 投票，**只在 G2/G3/G4 閘門跑**（省 token）|
| Eval ≥ 80% | SC-002/G3 | 130 題**達標率 ≥ 80%**；CP ≥ 0.85 / Faithfulness ≥ 0.90 / AR ≥ 0.85 |
| Eval 報告 | G4 | 130 題 + 場景 4 成績、圖表、解讀；含買賣建議 = 0 的證據 |

## 3. Tasks by Week（可勾選）

> **📌 2026-06-04 進度快照（PM 站會）**
> Ragas pipeline / 130 題題庫 / 評分 CI **Drive+repo 查無**（若在 Notion/gsheet 請本人補）；**Eval ≥80% 是 G3 硬門檻**。
> - **可即刻開工、不必等 R4**：系統 fallback 模式已能端到端跑（`build_workflow().invoke()` 直接收 answer/contexts/golden 四件套）。開工指南 [`../R5_eval_開工指南.md`](../R5_eval_開工指南.md)。
> - **本週就做**：fallback 跑通 Ragas + 起 25 題題庫（題目借 R6 Ontology + R1 場景）。
> - 下方任務維持未勾（W1 分數為煙測分、非真分）。

**W1**
- [ ] D1 Ragas 環境、能對假答案打分
- [ ] D2 題庫 25 題（財務 / 檢索基本題）
- [ ] D3 Ragas pipeline：自動跑一批出分
- [ ] D4 題庫到 50 題
- [ ] D5 G1 驗收（品質面）
- [ ] ⚠️ 註：W1 workflow 回假資料 → **W1 分數僅為 pipeline 煙測，真分從 W2 e2e 起算**

**W2**
- [ ] D6 題庫到 75 題
- [ ] D7 Ragas CI（每次 commit 自動跑分）
- [ ] D8 三方 Judge 投票
- [ ] D9 100 題完成
- [ ] D10 G2 驗收（評分管線上線）

**W3（最關鍵硬指標）**
- [ ] D11 Eval 迭代：跑分、列不及格題
- [ ] D12–13 Ragas Judge 三方投票穩定化
- [ ] D14–15 擴題到 130（含新聞 / 跨產業題）
- [ ] D16 **Eval 80% 衝刺**
- [ ] D17 G3：公布 Eval 分數（過閘關鍵）

**W4**
- [ ] D23 Eval 報告（130 + 場景 4 獨立 10 題、圖表）
- [ ] D24 G4：確認 Eval ≥ 80%（必要時續迭代）
- [ ] D25–27 彩排時提供「品質數據」話術給 R1

## 4. Dependencies
- **上游**：R6（出財務 / 紅隊題、場景 4 標註）、R2/R3（接系統輸出 / CI）。
- **下游**：R2/R3 靠你的「不及格題清單」知道要修什麼；R1 demo 靠你的分數當客觀證據。

## 5. Risks & Fallback
- 三方 Judge 成本高 → **只在閘門跑 3 模型，平常 CI 用 1 個 Flash**。
- 分數卡關 < 80% → 用「跑分→列最差題→回報 owner 修→再跑」迭代逼近；G3 沒過啟動降級（砍場景 3）。

## 6. Constitution 遵循
- **IV**：你是品質門檻的把關者，分數說了算，不以主觀感覺放行。
- **I**：Eval 報告須含「買賣建議 = 0」的量化證據（與 R6 紅隊對齊）。
