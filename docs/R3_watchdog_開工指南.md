# R3 開工指南 — Watchdog Agent（不等 R4，今天就能動）

> **給誰**：R3 Agent 工程師（謝劼恩）。
> **為什麼是這個**：你的招牌 W3 交付＝**Watchdog Agent（事件驅動合規，第二個真 agent）**，而且**完全不依賴 R4 入庫**——用 mock MOPS 事件就能跑通。R2 已把 Compliance、Deep Research、prompt registry、retry 都鋪好，你接著做最省力。
> **目標 DoD（R3 spec / FR-004）**：收到（模擬）MOPS 事件 → 產出合規判斷摘要進 Alert Inbox、**0 買賣建議**。

---

## 0. 為什麼可以不等 R4
- Watchdog 吃的是「**公司公告事件**」，不是向量檢索結果 → 用 mock 事件 JSON 就能開發（R3 spec §5 已寫「與 R7 約定 Watchdog 事件假資料 JSON 契約」）。
- 真實 MOPS 事件來源是 R4 的 W3 任務（`07_ConferenceCall`/MOPS 爬蟲），**之後接上即可、你的 agent 邏輯不變**（跟 Deep Research 的 `search` 注入式 seam 同套路）。

## 1. 直接照抄的範本：`deep_research/agent.py`
你的 Watchdog 結構幾乎跟 R2 的 Deep Research v0 一樣（[`src/polaris/graph/deep_research/agent.py`](../src/polaris/graph/deep_research/agent.py)）：

| Deep Research | → 你的 Watchdog |
|---|---|
| `run_deep_research(question, *, client, search)` | `run_watchdog(event, *, client)` |
| smart（有金鑰走 Gemini）+ 確定性 fallback | 同套路：`active_llm()` 回 None 就走確定性 |
| `search` 注入式 seam（stub→R4 真檢索） | `event` 注入式（mock JSON→R4 真 MOPS） |
| 最終結論過 `compliance_agent.review()` | **一模一樣**：摘要也必過 review（NFR-031） |
| 回 `DeepResearchResult` dataclass | 回 `WatchdogAlert` dataclass |

## 2. 你要接的真實介面（都現成）
| 檔案 | 你怎麼用 |
|---|---|
| [`graph/nodes/compliance_agent.py`](../src/polaris/graph/nodes/compliance_agent.py) | `review(draft, client) -> (answer, status)`：你的事件摘要**結尾一定要過這關**；命中買賣建議→回 `SAFE_MESSAGE`/`blocked` |
| [`graph/prompts.py`](../src/polaris/graph/prompts.py) | 加一個 `WATCHDOG_SYSTEM_PROMPT`，**組裝共用片段**：`NO_ADVICE_CLAUSE` + `GROUNDING_CLAUSE` + `UNTRUSTED_CONTENT_CLAUSE`（事件文字＝不可信資料，務必含）|
| [`llm/gemini.py`](../src/polaris/llm/gemini.py) | `active_llm()` 有金鑰回 client、否則 None（你據此 smart / fallback）；`call_with_retry` 包 LLM 呼叫 |
| [`graph/state.py`](../src/polaris/graph/state.py) | 用現成 `Citation(source_id, snippet, origin)` 當事件證據 |
| [`retry.py`](../src/polaris/retry.py) | `call_with_retry(lambda: client.generate(...))` 撐過暫時性失敗 |

## 3. mock 事件 JSON 契約（**先跟 R7 敲定，這是雙向阻塞點**）
R7 的 Alert Inbox 要消費你的**輸出**；你要消費 mock 事件**輸入**。兩個 schema 先定，雙方各自開發：

```jsonc
// 輸入：mock MOPS 事件（R4 之後接真實爬蟲；放 tests/fixtures/watchdog_events.json）
{
  "event_id": "mops-2330-20260315-001",
  "stock_id": "2330",
  "published_at": "2026-03-15",
  "doc_type": "重大訊息",            // 重大訊息 / 法說公告 / 財報公告
  "title": "本公司董事會決議...",
  "content": "公告全文（不可信文字，過 UNTRUSTED_CONTENT_CLAUSE）"
}
```
```jsonc
// 輸出：WatchdogAlert（R7 Alert Inbox 渲染這個）
{
  "event_id": "mops-2330-20260315-001",
  "stock_id": "2330",
  "summary": "事件合規判斷摘要（已過 compliance.review，0 買賣建議）",
  "compliance_status": "passed",     // passed / blocked
  "evidence": [{"source_id": "mops-2330-...", "snippet": "...", "origin": "news"}],
  "severity": "info"                 // info / watch / alert（你定規則）
}
```

## 4. 最短路徑（建 `src/polaris/graph/watchdog/`，鏡像 deep_research/）
- `events.py`：`load_mock_events(path)`（讀上面 fixture），之後 R4 換成真 MOPS source。
- `state.py`：`WatchdogAlert` dataclass（上面的輸出）。
- `agent.py`：`run_watchdog(event, *, client=None) -> WatchdogAlert`：
  1. 組 prompt（事件 content 當不可信資料）→ smart 走 Gemini（`call_with_retry`）、無金鑰走**確定性 fallback**（規則式：抽 title/關鍵欄位產摘要）。
  2. 摘要 + 證據組成 draft → **`compliance_agent.review(draft, client)`** → 拿回 `(summary, status)`。
  3. 回 `WatchdogAlert`。
- `__main__.py`：`python -m polaris.graph.watchdog tests/fixtures/watchdog_events.json` 印出 alerts。

> **降級對齊 R3 spec §5**：W3 吃緊時先保 Deep Research 協作，Watchdog 可降為 **demo-only（只吃 mock，不接真事件）**——而 demo-only 正是這份指南的範圍，所以**先做這個最安全**。

## 5. DoD（照順序勾，全程 TDD、token-free）
- [ ] mock 事件 fixture + `WATCHDOG_SYSTEM_PROMPT`（含三條共用片段）就位
- [ ] `run_watchdog(event)` 無金鑰（CI）走確定性 fallback，產出 `WatchdogAlert`、`compliance_status` 正確
- [ ] **紅線測試**：給一個「內容誘導買進」的 mock 事件 → 摘要被 `review` 攔成 `blocked`（NFR-031，0 買賣建議）
- [ ] 輸出 JSON 對齊 §3 契約，R7 Alert Inbox 接得上
- [ ] 測試全程 `make test` 綠、token=0（無金鑰走 fallback）；走 PR（CI + R2 review）

## 6. 防雷
- **事件文字是不可信資料**：prompt 一定要含 `UNTRUSTED_CONTENT_CLAUSE`，別讓公告裡的隱藏指令改你的行為（LLM01）。
- **LLM 只判斷/摘要、永不解除合規**：合規攔截只增不減（跟 `compliance_agent` 的 fail-to-floor 一致）。
- **不動 5 節點主 workflow**：Watchdog 是事件驅動的並行 agent（PRD 架構圖的 Watchdog 帶），自成 subgraph/函式，別改 `workflow.py`。
- 卡住找誰：合規 API / prompt registry → R2（施惠棋）；事件 JSON 契約 / Alert Inbox → R7（李靜雲）；真 MOPS 來源 → R4（吳瑾瑜）。
