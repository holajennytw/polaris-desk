# G3 架構面驗收自評（R2）

> **閘門**：W3 D17 G3（架構面）。本文是 R2 對「G3 四條件的 R2 負責項交付狀態」的自評，
> 對應 spec 的 FR-004 / SC 與 R2 角色 spec 的 W3–W4 交付（D11–D16＋後續）。
> 每條都附**可重跑的證據**（測試名 / 指令）。
>
> **G3 四條件**（`00_Polaris-Desk_專題_spec.md` §閘門表）：**ColPali/LLMLingua 整合 + Eval ≥ 80% +
> Deep Research 可跑 + Watchdog 可跑**（ColPali 失敗 → 砍場景 3 + ColPali）。其中 **R2 直接負責**＝
> Deep Research 可跑、LLMLingua 的**量測**半邊；Eval ≥ 80%＝R5（Ragas 真分）、Watchdog＝R3。
> 四條件逐項 owner 簽核的**完整驗收清單＝R1 的卡**（R1 spec D15–16），本文不越界。

更新時間：2026-06-16 ｜ 全測試：`make lint && make test` → **586 passed, 6 skipped, ruff clean**
｜ 開發路徑：branch `claude/r2-tasks-rqbcjr`（PR #72）

---

## A. G3 四條件 × R2 對應狀態

| G3 條件 | owner | R2 視角狀態 | 證據 / 備註 |
|---|---|---|---|
| **Deep Research 可跑** | **R2** | ✅ | v0 loop 跑通（D15）+ v1 過驗收（D16）；v2 ReAct 接 LLMLingua 壓縮（PR #72）；預設 search = `active_search_fn(viewer)`（BM25 + vector + Cohere Rerank）；見 §C 場景 2 四門檻 |
| **LLMLingua** 整合 | **R2**（量測 + **live**）| ✅ | 量測 harness ✅；**真 LLMLingua-2 已實測達 SC-006 ≥50%**（55.83%）；**live 接入** `active_compressor().compress()` 在 Writer node `_build_prompt()` 呼叫（PR #72）；`POLARIS_USE_LLMLINGUA=1` 啟用；CI token=0（DeterministicCompressor 預設）|
| **ColPali 整合** | R4（**TD-01 cut**）| ✅ 已裁定 cut | **2026-06-14 TD-01**：R4 未開工 POC，R1/R2 backup 評估後確定 cut。ColPali 從 G3 必要條件移除；retrieval 鎖定 3-path（BM25 + vector + **Cohere Rerank**，見 §B）。G3 不設 ColPali 閘門（spec contingency 已啟用）|
| **Eval ≥ 80%** | R5 | ⤷ 跨角色 | 130 題 Ragas + 三方 Judge（CP≥0.85 / Faithfulness≥0.90 / AR≥0.85）；R5 spec D17 公布分數。**R2 已備妥管線骨架（75 題 smoke 100%）**：`python -m polaris.eval` |
| **Watchdog 可跑** | R3 / **R2 代填** | ✅ | Phase 1 全實作（events/state/agent/notify）；CLI demo 無需引數（內建 5 筆事件）；`--notify` 旗標接 NotificationService 全管線；GET /alerts API 端點；576 passed |

---

## B. R2 W3–W4 架構面交付（D11–D16 ＋ 後續，皆已或即將併入 main）

| 交付 | 對應 | 狀態 | 證據（可重跑）|
|---|---|---|---|
| D11 狀態管理 / AQ-03 拍板 | FR-004 | ✅ | 設計文件 `docs/superpowers/specs/...d11...`；決策＝**自寫 ReAct loop** |
| D13 Agent prompt 優化 | FR-004 | ✅ | `test_prompts.py`、`test_deep_research_react.py`；中央 registry `graph/prompts.py` |
| D15 Deep Research v0 | FR-004 | ✅ | `test_deep_research_agent.py`；純 Python bounded loop |
| D16 Deep Research v1 | FR-004 | ✅ | `test_deep_research_acceptance.py`；is_fully_traceable + verify-or-synthesize |
| **issue #32 R2 seam** | 存取控制 | ✅ | `ResearchState.viewer` 欄位；`cli ask --viewer`；`/ask /research viewer` 欄位；viewer 全鏈透傳至 store.search；`POST /research viewer` → `run_deep_research(viewer=...)` → `active_search_fn(viewer)` |
| **HybridRetriever 3-path + active_search_fn** | 檢索架構 | ✅ | BM25 + vector + **Cohere Rerank**（`rerank_fn` 注入式，無 API key 優雅 skip）；`make_retriever_search_fn` / `active_search_fn(viewer)` SearchResult→Citation 橋；Deep Research 預設 search = `active_search_fn(viewer)`；`test_retriever.py` 15 tests |
| **D8 live LLMLingua 接入** | 壓縮 | ✅ | `writer_agent._build_prompt()` 呼叫 `active_compressor().compress()`；`test_writer_agent.py::TestBuildPromptCompression` 4 tests；不影響 Citation grounding |
| **owner/confidential schema** | issue #32 R4 側 | ✅ | pgvector + BigQuery 兩後端 SQL 過濾；schema migration SQL（待 R4 執行）|
| **Watchdog demo 改善** | G3 demo 備戰 | ✅ | `__main__.py` 無需引數（預設 `watchdog_events.json`）；`--notify` 旗標；`/alerts` API |
| **Eval 管線骨架** | specs/004 | ✅ | 75 題 smoke 100%；`python -m polaris.eval`；報告誠實標「煙測分」|

---

## C. Deep Research v1 驗收證據（場景 2：同業比較）

驗收題：「比較台積電與聯發科最近兩季的毛利率變化」。`test_deep_research_acceptance.py::TestAcceptanceScenario2`
對 `run_deep_research(...)` 斷言四門檻全過、且**可重現**（同輸入兩跑 final_answer / iterations 完全相同）：

| FR-004 門檻 | 斷言 | 機制 |
|---|---|---|
| ≤ 6 次 ReAct 迴圈 | `iterations <= 6` | `should_continue(max_loops=6)` 硬編碼上限 |
| ≥ 3 條引用 | `len(evidence) >= 3` | 確定性 facet 政策（營收/毛利率/風險）輪流 search 到 ≥3 才 finish |
| 句句可溯源 | `is_fully_traceable(answer, evidence)` | verify-or-synthesize 硬保證 |
| 0 買賣建議 | `all(kw not in answer for kw in BUYSELL_KEYWORDS)` | 最終結論過 D9 Compliance（NFR-031）|

---

## D. 核心不變量（W1 起持續綠）

| 準則 | 內容 | 狀態 | 證據 |
|---|---|---|---|
| SC-001/002 | e2e 產出 answer+citations、trace 列 5 節點 | ✅ | `test_workflow_e2e.py` |
| SC-003 | 6 關鍵字攔截 100%、最終 answer 0 買賣建議 | ✅ | `test_compliance.py`、`test_compliance_agent.py` |
| SC-005 | 換節點 → workflow.py diff = 0 行 | ✅ | `test_node_swap.py` |
| SC-006 | 同問題 3 次結果完全相同 | ✅ | `test_workflow_e2e.py::TestE2EDeterminism`；Deep Research 亦可重現 |
| SC-007 | 空輸入只跑 Planner、固定錯誤訊息 | ✅ | `test_workflow_edges.py` |
| NFR-031 | 任何路徑 0 買賣建議 | ✅ | Security `test_never_recommends_buy_sell`；Watchdog NFR-031 gate；eval 紅隊題 10/10 |
| issue #32 | 跨租戶隔離 — analyst_A 看不到 client_B 文件 | ✅ | `test_cross_tenant_isolation_contract`（PASSED）；`test_retriever_bm25_viewer_filter_blocks_owner_scoped`；`test_retriever_viewer_filter_passed_to_store` |

---

## E. 上游依賴 / Action items（R2 視角）

| 項目 | 由誰 | 影響 | 狀態 |
|---|---|---|---|
| Eval ≥ 80%（Ragas + 三方 Judge）| **R5** | G3 硬門檻（`context_precision≥0.85 / faithfulness≥0.90 / AR≥0.85`）| ⏳ R5 spec D17 公布；R2 管線就緒 |
| migration SQL 執行 | **R4** | `migrations/2026-06-14_add_owner_confidential.sql`（pgvector）＋ `..._bq.sql`（BigQuery） | ⏳ R4 在 ingestion 後執行 |
| `polaris_core` 真實語料入庫 | **R4** | 真分 Ragas 需要；目前 stub 語料 | ⏳ R4 ingestion SOP §4 |
| COHERE_API_KEY 設定 | **全員** | Cohere Rerank 啟用（無 key → 優雅 skip，不阻 CI） | ⏳ Secret Manager 設定 |
| ColPali | ~~R4~~ **TD-01 cut** | G3 場景 3 砍除 | ✅ 已裁定 |
| 視覺檢索第 4 路（接既有 colpali_pages）| **R3/R4** | **TD-02（提案，待 PM 簽核）**：逆轉 TD-01 檢索整合決定。查證後事實——R4 早已將圖表頁以 ColPali 入庫（`polaris_core.colpali_pages`，5701 頁、20 tickers、128 維池化向量），僅 R3 未接。本案接上既有表為**第 4 路（gated，場景 3 專用）**，`origin="colpali"`，**零資料架構變更**（只讀既有表，不動 chunks 768 庫）。Phase 1 檢索+命中率（≥70%），Phase 2 vision 讀數字回答。依賴 R4 提供 query encoder。設計見 `docs/superpowers/specs/2026-06-20-restore-4th-retrieval-path-vision-design.md` | ⏳ 待 PM 簽核 |
| Cloud Run 部署（6/15）| **R4/R7** | 需 GCP 憑證 | ⏳ 不在 R2 範圍 |

---

## F. G3 結論（R2 視角，2026-06-15 更新）

**R2 架構面 → Go**：

- **Deep Research** v1 已過驗收（場景 2 四門檻）；預設 search 升級為 `active_search_fn(viewer)`（BM25 + vector + Cohere Rerank）。
- **LLMLingua** 量測 ≥50% 完成 **+ live 接入** Writer node（`POLARIS_USE_LLMLINGUA=1`；CI token=0）。
- **ColPali** TD-01 cut，retrieval 鎖定 3-path（BM25 + vector + Cohere Rerank）。
- **Issue #32 存取控制**全鏈就緒（viewer → state → CLI → `/ask` → `/research` → `active_search_fn` → HybridRetriever → store SQL）。
- **Watchdog** demo 備妥（CLI、API、NotificationService 全管線）。
- **Eval 管線** 75 題 smoke 100%（誠實標「煙測分」，G3 真分待 R5）。

全套件：**586 passed, 6 skipped, ruff clean**（`make lint && make test`）。

**整體 G3 是否過閘取決於跨角色硬門檻**：Eval ≥ 80%（R5 Ragas 真分）＋ Cloud Run 部署（R4/R7）。
建議 **R1 彙整 4 條件逐項 owner 簽核**（R1 spec D15–16）作為 G3 最終裁定。
