# Feature Specification: Watchdog Agent（事件驅動合規 Agent）

**Feature Branch**: `r2/003-watchdog-agent`
**Created**: 2026-06-10
**Status**: Implemented
**Owner**: R2（Tech Lead，鏡像 Deep Research 骨架）；R3 接手後換真 MOPS 事件源
**上位文件**: 憲法 v2.0.0 §I (NFR-031)、`docs/R3_watchdog_開工指南.md`

---

## 一句話

MOPS 公告事件（mock→R4 真爬蟲）→ Watchdog Agent → 合規摘要 WatchdogAlert，
每則摘要都過 Compliance Gate（0 買賣建議），供 R7 Alert Inbox 消費。

---

## User Stories

### US1 — 合規 Watchdog 掃描一則公告，產出 WatchdogAlert（P1，MVP）

**Goal**: `run_watchdog(event)` 對任一 MopsEvent 產出 WatchdogAlert，
summary 已過 Compliance Gate、evidence 有接地引用、severity 依 doc_type 決定。

**Independent Test**: 餵一筆 mock 重大訊息事件 → `alert.compliance_status == "passed"`、
`alert.severity == "alert"`、`alert.evidence` 非空。

**Acceptance Scenarios**:
1. **Given** 正常公告事件，**When** `run_watchdog(event, client=None)`，
   **Then** alert 有 summary（確定性 fallback）、compliance_status="passed"、evidence 有 source_id。
2. **Given** content 含「建議買進」，**When** `run_watchdog(event)`，
   **Then** compliance_status="blocked"、summary 為 SAFE_MESSAGE（0 買賣建議外溢）。
3. **Given** 有 LLM client，**When** `run_watchdog(event, client=client)`，
   **Then** 優先走 Gemini 產摘要；LLM 失敗自動退確定性 fallback（不掛掉）。

---

## Functional Requirements

| FR | 描述 |
|----|------|
| FR-W-001 | `run_watchdog(event, *, client=None) -> WatchdogAlert` 為唯一公開入口 |
| FR-W-002 | client=None 走確定性 fallback（token=0，CI 用）；有 client 走 Gemini Flash |
| FR-W-003 | 任何 LLM 失敗（含 retry 用盡）→ 退 fallback，不拋給呼叫端 |
| FR-W-004 | summary 一律過 `compliance_agent.review()`（NFR-031 出口守衛）|
| FR-W-005 | severity 由 doc_type 決定（確定性規則），不由 LLM 決定 |
| FR-W-006 | evidence 至少 1 條 Citation（事件本身，接地原則 §II）|
| FR-W-007 | event.content 視為不可信資料（UNTRUSTED_CONTENT_CLAUSE 進 prompt，LLM01）|
| FR-W-008 | `workflow.py` 零 diff（Watchdog 是並行 agent，不改 5 節點主 workflow）|

---

## Non-Functional Requirements

| NFR | 描述 |
|-----|------|
| NFR-W-001 | 同事件兩次 `run_watchdog` 結果完全一致（確定性，SC-NC-004）|
| NFR-W-002 | CI token=0、0 外呼（fallback 走確定性）|
| NFR-W-003 | 紅隊事件（含買賣建議）0 穿透（NFR-031）|

---

## Out of Scope（Phase 1）

- R4 真實 MOPS 爬蟲接入（Phase 2，R4 W3）
- R7 Alert Inbox UI 渲染（R7 消費 WatchdogAlert 契約）
- 多事件批次處理 / 排程（Phase 2）
- 事件去重（不同 event_id 視為不同事件）
