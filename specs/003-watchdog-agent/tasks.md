# Tasks: Watchdog Agent Phase 1

**Input**: `specs/003-watchdog-agent/spec.md`、`docs/R3_watchdog_開工指南.md`
**Tests**: TDD、全程 token=0、0 真實外呼

## Phase 1: 核心實作

- [X] T001 `src/polaris/graph/prompts.py` 加 `WATCHDOG_SYSTEM_PROMPT`（NO_ADVICE + GROUNDING + UNTRUSTED_CONTENT 三片段）
- [X] T002 `src/polaris/graph/watchdog/events.py` — `MopsEvent` frozen pydantic + `load_mock_events()`
- [X] T003 `src/polaris/graph/watchdog/state.py` — `WatchdogAlert` dataclass + `classify_severity()` 規則
- [X] T004 `src/polaris/graph/watchdog/agent.py` — `run_watchdog(event, *, client=None)`：fallback + smart + compliance gate
- [X] T005 `src/polaris/graph/watchdog/__init__.py` 公開 API re-export
- [X] T006 `src/polaris/graph/watchdog/__main__.py` CLI demo
- [X] `tests/fixtures/watchdog_events.json` — 5 筆（4 正常 + 1 紅隊）
- [X] `tests/test_watchdog_agent.py` — 24 tests：模型驗證、severity 分級、fallback、NFR-031 紅線、smart 層、CLI smoke
- [X] 全套件回歸：475 passed / 6 skipped，ruff clean，`workflow.py` 零 diff

## Phase 2（不在本 PR）

- [ ] R4 真實 MOPS 爬蟲接入（event_id / content 來自 MOPS API）
- [ ] R7 Alert Inbox UI 消費 `WatchdogAlert`
- [ ] 批次排程（定期掃描新公告）
- [ ] 接 NotificationService：`run_watchdog()` → `NotificationService.publish(watchdog_alert_event)`
