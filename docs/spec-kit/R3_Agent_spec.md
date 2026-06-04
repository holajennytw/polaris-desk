# 角色規格書（Spec Kit）：R3 — Agent 工程師

**Role**: R3 4-way 檢索 + Writer 引用 + Watchdog Agent **色**：冰藍
**對應**：專題 spec FR-002/003/004/006；4 週計畫 R3 卡 **Status**: 尚未開工（2026-06-04；開工指南已備）

## 1. Mission
做出「會找資料的搜尋員」（4-way 檢索）、讓答案逐句有憑有據（Writer 引用 + Calc grounding），W3 主導第二個真 Agent（Watchdog 事件驅動合規）。
- **In scope**：Retriever（BM25 / 向量 / ColPali 接 / Cohere Rerank）、Writer 引用、Compliance 整合、LLMLingua 整合、Watchdog Agent、新聞評估卡。
- **Out of scope**：LangGraph 編排骨架（R2）、資料入庫 / ColPali 訓練（R4）、評分（R5）。

## 2. Deliverables & Acceptance Criteria

| 交付物 | 對應 | 可驗收標準（measurable）|
|---|---|---|
| Retriever（W1 先 2 路）| FR-002/G1 | 能從入庫法說稿撈出相關段落；W1 **≥ 2 路（BM25+向量）可動**，其餘 W2 補 |
| 4-way + Rerank | FR-002/G2 | W2 補齊向量 / ColPali / Cohere Rerank（`client.v2.rerank`, `rerank-v4.0`）|
| Writer 逐句引用 | FR-003/SC-007 | **答案每句標出處、數字附來源**（Calc grounding）|
| Watchdog Agent | FR-004/G3 | 收到（模擬）MOPS 事件 → 產出合規判斷摘要進 Alert Inbox、**0 買賣建議** |
| 新聞評估卡 | FR-006 | 只描述 / 標證據 / 標矛盾，**不得出買賣建議**（NFR-031）|

## 3. Tasks by Week（可勾選）

> **📌 2026-06-04 進度快照（PM 站會）**
> GitHub 0 commit；Retriever/Writer/Compliance/LLMLingua/Deep Research 目前是 R2 代寫的骨架，**R3 招牌 Watchdog Agent 尚未開始**。
> - **開工指南已備**：[`../R3_watchdog_開工指南.md`](../R3_watchdog_開工指南.md)——用 mock MOPS 事件、**不必等 R4**。
> - **本週就做**：接 Watchdog Agent（鏡像 `deep_research/agent.py`、接 `compliance_agent.review`、與 R7 定事件 JSON 契約）。
> - 下方任務維持未勾（尚無產出）。

**W1**
- [ ] D1 Agent 開發環境、能呼叫 Gemini（`google-genai`）
- [ ] D2 Retriever v0（關鍵字找得到）
- [ ] D3 **先做 2 路**：BM25 + 向量語意（ColPali/Rerank 留 W2，因 ColPali POC 在 W2）
- [ ] D4 把 Retriever 接進 Planner
- [ ] D5 G1 驗收（檢索面）— 至少 2 路可動

**W2**
- [ ] D6 Retriever rerank（Cohere `rerank-v4.0`）
- [ ] D7 Writer + 引用（逐句標出處）
- [ ] D8 Calc grounding（數字附來源）
- [ ] D9 Compliance 檢查整合進輸出
- [ ] D10 G2 驗收（檢索 / 寫作面）— 4 路到位、逐句引用

**W3（+3.5 人天 · 最忙）**
- [ ] D11 LLMLingua 整合（量 token 省幅）
- [ ] D12 Compliance role B
- [ ] D13 Constitutional（agent 自我行為憲法）
- [ ] D14 **Watchdog 設計凍結**（接什麼事件、查什麼）
- [ ] D15–16 Watchdog v0 + Deep Research 協作 + 新聞評估卡（守 NFR-031）

**W4**
- [ ] D18 Watchdog 強化到 demo 等級（穩定觸發 + 合規判斷準）
- [ ] D20–21 供部落格 2（Deep Research）、3（Watchdog cron→event）技術內容
- [ ] D24 G4：兩個 Agent 上線驗收
- [ ] D25–27 彩排：確保 agent 場景不出錯

## 4. Dependencies
- **上游**：R4（倉庫接口 / ColPali / Watchdog 事件來源 / 新聞表）、R2（LangGraph 整合 / Deep Research）、R6（合規規則）。
- **下游**：R5 用 Eval 驗你的引用正確性；R7 的 Citation Tracer / Alert Inbox 接你的輸出格式。

## 5. Risks & Fallback
- W3 +3.5 人天最吃緊 → **🛟 降級：先保 Deep Research 協作，Watchdog 降為 demo-only（不接真實事件）**。
- ColPali 未上線（看 R4 POC）→ Retriever 先跑 BM25+向量+Rerank 3 路，ColPali 上線再補。
- **與 R7 約定 Watchdog 事件假資料 JSON 契約**（W2 內定），避免 R7 的 Alert Inbox 沒資料可接。

## 6. Constitution 遵循
- **I（NFR-031）核心守門人**：Compliance 整合 + 新聞卡 + Watchdog 都必須攔買賣建議（= 0）。
- **II**：Writer 沒來源不得輸出結論句。
