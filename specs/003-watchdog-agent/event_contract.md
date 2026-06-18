# Watchdog 事件契約（input / output）+ Demo 驗收

> 對應 `specs/003-watchdog-agent/spec.md`、`src/polaris/graph/watchdog/`。
> **生產者**（R4 MOPS 來源）依 `MopsEvent` 產事件；**消費者**（R7 Alert Inbox）依 `WatchdogAlert` 渲染。
> 此契約是 R3 自己可掌控的部分；R4／R7 各自照本檔開發即可，agent 邏輯不變（注入式 seam）。

---

## 1. 輸入契約：`MopsEvent`（生產者 → Watchdog）

`src/polaris/graph/watchdog/events.py`，pydantic **frozen**。

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `event_id` | string | ✅ | 事件唯一鍵（去重用；不同 id 視為不同事件） |
| `ticker` | string | ✅ | 公司代號，例 `2330` |
| `published_at` | datetime (ISO) | ✅ | 公告時間 |
| `doc_type` | enum | ✅ | `重大訊息` / `法說公告` / `財報公告` / `其他` |
| `title` | string | ✅ | 公告標題 |
| `content` | string | — | 公告全文。**視為不可信資料（LLM01）**；prompt 已含 `UNTRUSTED_CONTENT_CLAUSE` |

```jsonc
{
  "event_id": "mops-2330-20260610-001",
  "ticker": "2330",
  "published_at": "2026-06-10T09:00:00",
  "doc_type": "重大訊息",
  "title": "台積電 董事會決議通過現金增資",
  "content": "本公司董事會決議通過現金增資 500 億元，以供先進製程擴廠所需資金。"
}
```

> R4 真實 MOPS 爬蟲上線後，只要產出符合本 schema 的物件即可（mock JSON → 真來源，`run_watchdog` 不動）。

---

## 2. 輸出契約：`WatchdogAlert`（Watchdog → 消費者）

`src/polaris/graph/watchdog/state.py`，dataclass。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `event_id` | string | 對應輸入事件 |
| `ticker` | string | 公司代號 |
| `summary` | string | 中立事件摘要（**已過 Compliance Gate**） |
| `compliance_status` | enum | `passed` / `blocked` |
| `severity` | enum | `info` / `watch` / `alert` |
| `evidence` | `Citation[]` | 至少 1 條接地引用（`source_id` / `snippet` / `origin="news"`） |

```jsonc
{
  "event_id": "mops-2330-20260610-001",
  "ticker": "2330",
  "summary": "【重大訊息】2330 …（已過合規、0 買賣建議）",
  "compliance_status": "passed",
  "severity": "alert",
  "evidence": [{ "source_id": "mops-2330-20260610-001", "snippet": "…", "origin": "news" }]
}
```

> R7 Alert Inbox 也可直接打後端 `GET /alerts`（token-free，回 `WatchdogAlert[]`）取得渲染資料。

---

## 3. 規則（確定性、不由 LLM 決定）

**severity 由 `doc_type` 決定**（`classify_severity`）：

| doc_type | severity |
|---|---|
| 重大訊息 | `alert` |
| 法說公告 / 財報公告 | `watch` |
| 其他 | `info` |

**合規語意（NFR-031）**：
- `summary` 一律過 `compliance_agent.review()`；命中買賣建議 → `compliance_status="blocked"`、`summary` 換成 `SAFE_MESSAGE`。
- 通知橋接 `watch_and_notify()`：`blocked` → **不發 user 通知**、改發固定模板 internal 告警（**被攔原文不外溢下游**）；`passed` → 過第 2 閘後入通知中心。

**保證**：`client=None` 走確定性 fallback（token=0、0 外呼）；同事件兩次 `run_watchdog` 結果一致；LLM 任何失敗 → fail-to-deterministic，不拋給呼叫端；`workflow.py` 零 diff（並行 agent）。

---

## 4. Demo / 驗收指令

```bash
# 1) CLI demo：掃 mock 事件、印 alerts 與 passed/blocked 統計
python -m polaris.graph.watchdog src/polaris/graph/watchdog/data/watchdog_events.json

# 2) 一鍵驗收（token-free，斷言契約 + NFR-031；exit 0=PASS / 1=FAIL）
python scripts/accept_watchdog.py

# 3) Alert Inbox 後端（R7 對接）
python -m polaris.api    # 然後 GET /alerts

# 4) 單元測試
.venv/bin/pytest tests/test_watchdog_agent.py tests/test_watchdog_notify.py tests/test_watchdog_accept.py -q
```

**PASS 樣貌**：內建 5 事件 → `passed=4 blocked=1`；紅隊事件（`mops-9999-redteam-001`，內文含「建議買進」）被攔成 `SAFE_MESSAGE`；整體輸出 **0 買賣建議**；severity 分級正確。

---

## 5. 不在 R3 掌控內（外部 owner / blocker）

| 項目 | Owner | 現況 |
|---|---|---|
| 真實 MOPS 事件來源（取代 mock JSON） | R4 | 待真爬蟲；接同一 `MopsEvent` schema 即可 |
| Alert Inbox UI 實渲染 | R7 | 後端 `/alerts` 契約已備，前端待接 |
| 批次排程（定期掃新公告） | R4 / R2 | Phase 2，未排 |
| 上雲（Cloud Run + Secret Manager） | R2 | G4，待部署 |

> 在上述上線前，Watchdog 以 **demo-only mock 事件**運作（spec §5 既定降級路線），且本契約／驗收已可獨立成立。
