# Feature Specification: Gemini 接地觸點實作

**Feature Branch**: `005-gemini-grounding`
**Created**: 2026-06-26
**Status**: Ready for implementation
**Owner**: R2（Tech Lead）
**上位文件**: 憲法 §II（引用接地）、§I（NFR-031）、[決策選單](../../docs/Gemini接地觸點_盤點與選單.md)

---

## 一句話

把專案中「面向使用者、輸出事實與數字」的出口從確定性模板升級成 Gemini 潤飾敘事，並加裝**可重用的引用驗證閘門** + **確定性 fallback**，讓任一出口的接地都能一次設計、多處共用。

---

## 優先順序

| 優先 | 觸點 | 說明 |
|------|------|------|
| **P0** | Deep Research 收尾 `/research` | 閘門純函式 + LLM 潤飾層 |
| **P1** | 同業比較 `/peer-compare` | 重用 P0 閘門，加 synthesis prompt |
| **P2** | 矛盾偵測 `/contradiction` summary | YAGNI 暫緩 |
| **P2** | `daily_status` 角色摘要 | 估 token 成本後決定 |
| **P3** | 提示問句 `/suggestions` | 免接地，只加 NO_ADVICE_CLAUSE |

---

## User Stories

### US1 — Deep Research 可產出流暢帶引用的敘事段落（P0）

`run_deep_research` 在 `DEEP_RESEARCH_LLM_SYNTHESIS=1` + 有金鑰時，呼叫 Gemini Flash 把確定性條列潤飾成敘事段落，結果過 `is_traceable_prose` + `numbers_grounded` 閘門；不過閘門 / 無金鑰 / LLM 例外 → 退回確定性條列（現狀），行為 byte-identical。

### US2 — 閘門純函式可被其他觸點共用（P0 產出）

`is_traceable_prose(text, evidence)` + `numbers_grounded(text, evidence)` 作為純函式放在 `deep_research/state.py`，任何 P1/P2 直接 `import` 使用。

### US3 — peer-compare 可產出「孰強孰弱、差異原因」敘事結論（P1）

`peer_compare` 在 `PEER_COMPARE_LLM_SYNTHESIS=1` 時，在現有引用表上加一段 Gemini 生成的比較敘事，敘事禁止暗示買賣（`NO_ADVICE_CLAUSE` + compliance 過濾），不過 → 退確定性摘要（現狀）。

### US4 — 所有接地出口有可觀測的採用率（P0）

每次 synthesis 記錄 `outcome`（`polished / gate_failed / llm_error / no_key / compliance_rejected / fallback`），可用 `grep deep_research.synthesis` 統計 prod 採用率。

---

## Functional Requirements

| FR | 描述 |
|----|------|
| FR-G-001 | `is_traceable_prose(text, evidence)` → bool：prose 中所有「（來源：sid）」的 sid ∈ evidence，且 ≥1 個標記 |
| FR-G-002 | `numbers_grounded(text, evidence)` → bool：prose 中所有數字 token 都能在 evidence snippets 中找到對應；抽數字前先移除所有 source-tag 子串（防止 sid 內數字誤算）|
| FR-G-003 | P0 flag `DEEP_RESEARCH_LLM_SYNTHESIS`（預設 `0`）；P1 flag `PEER_COMPARE_LLM_SYNTHESIS`（預設 `0`） |
| FR-G-004 | 任何閘門失敗 / 例外 / 無金鑰 → 確定性 fallback（byte-identical 現狀）；不靜默丟錯 |
| FR-G-005 | 每次 synthesis 結果記 `outcome=<狀態>` 到 logger，七種狀態見 §5 風險 R6 |
| FR-G-006 | LLM synthesis prompt 包含三條款（`GROUNDING_CLAUSE + NO_ADVICE_CLAUSE + UNTRUSTED_CONTENT_CLAUSE`）+ 「只改寫 base、不新增事實、保留（來源：sid）」|
| FR-G-007 | P1 `peer_compare` synthesis 最終過 `compliance_agent.review`；命中買賣建議關鍵字 → 退 fallback + `outcome=compliance_rejected` |
| FR-G-008 | flag 關閉時，整條路徑完全跳過 LLM，CI token=0 + 確定性 |

## Non-Functional

- NFR-G-001：flag 關閉時 CI token=0（禁用金鑰也不呼叫 LLM）。
- NFR-G-002：P1 閘門 import 自 P0 `deep_research.state`，不重複實作。
- NFR-G-003：不改現有函式簽名（`_synthesize`、`peer_compare`），避免連坐回歸。
- NFR-G-004：上 prod 前補 eval 題（P0: prose faithfulness Q136–Q139；P1: 比較式紅隊 Q131–Q134 + 正向 peer Q135）。題庫已遷至 R5 canonical `questions_v1.csv`。

## Out of Scope（本 spec）

- P2 `/contradiction` summary（YAGNI 暫緩）
- P2 `daily_status` 角色摘要（估 token 成本後另立 spec）
- ~~P3 `/suggestions` NO_ADVICE_CLAUSE~~ → ✅ 已實作（`_llm_suggestions`，flag `SUGGESTIONS_LLM` 預設關，免接地 + compliance 守門）
- 語意閘門（句↔來源語意比對）— P2 後補
- eval runner 支援 peer 路徑（P1 實作時一併補）
