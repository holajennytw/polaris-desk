# R7 開工指南 — 前端 / Demo（不等後端，用 mock JSON 先行）

> **給誰**：R7 Demo & 全端工程師（李靜雲）。
> **為什麼能現在做**：前端吃的是**固定形狀的 JSON**，不是後端本人。先跟 R2/R3 把 JSON 契約敲定、用 mock 餵 UI，**5 個畫面全部可以先做完**，最後把 mock 換成真 API 即可。
> **目標 DoD（R7 spec / SC-004/005/007）**：對話+引用 UI、Citation Tracer（點引用跳原文）、Alert Inbox、ReAct trace UI、RWD 無跑版、Vercel 上雲、Demo 備援影片。

---

## 0. 為何不等後端
- 後端的輸出**已經有確定形狀**（見 §2，都從現有程式碼抓出來的真欄位）→ 你照這形狀做 mock JSON，UI 先全做。
- 真 API 還沒有 HTTP 端點（目前只有 CLI / Python `build_workflow().invoke(...)`）→ **這是要跟 R2 敲的依賴**（見 §4），但**不擋你用 mock 開發**。

## 1. 技術選型（先決定，省得改兩次）
spec 寫「Next.js / Chainlit」二選一或混用。給你的建議：

| 路線 | 適合 | 取捨 |
|---|---|---|
| **Chainlit（推薦先做 demo）** | 對話 + 引用 + ReAct trace 的**核心 demo** | Python、最少前端碼、有內建 Step/Elements 可畫 trace 與引用；**團隊是 Python 強項**（你次手＝R2 施惠棋）→ 最快有可 demo 的東西 |
| **Next.js** | W4 **Landing Page + Vercel 上雲** | React 生態、最彈性、Vercel 原生；但前端工比 Chainlit 多 |

> **務實組合**：**核心 demo 用 Chainlit**（最快跑出對話+引用+trace），**Landing 用 Next.js / 靜態頁**（W4 配 R1 文案上 Vercel）。若你本來就熟 React，全 Next.js 也行。

## 2. 你要接的 JSON 契約（mock，這是核心）
以下欄位**都是後端現有程式碼的真實輸出**（`graph/state.py`、`deep_research/state.py`、R3 Watchdog 契約），照這個做 mock，之後零改動換真 API。

### (a) 問答回應（對話 + 引用 UI）
```jsonc
// build_workflow().invoke({"query": ...}) 的結果形狀
{
  "query": "台積電最近兩季毛利率？",
  "answer": "……（已過合規）",
  "compliance_status": "passed",        // passed / blocked / unknown
  "citations": [                         // 逐句引用 → Citation Tracer 用
    { "source_id": "stub-2330-2024Q3", "snippet": "法說頁X：毛利率…", "origin": "stub" }
    // origin: stub|bm25|embedding|colpali|rerank|news
  ],
  "trace": [                             // 每節點執行紀錄（可做「處理過程」視覺）
    { "node_name": "planner", "status": "ok", "elapsed_ms": 12,
      "input_keys": ["query"], "output_keys": ["plan","period"], "error_message": null }
  ]
}
```

### (b) Deep Research / ReAct trace UI
```jsonc
// run_deep_research(question) → DeepResearchResult
{
  "question": "比較台積電與聯發科毛利率",
  "final_answer": "- 論點…（來源：sid）",
  "evidence": [ { "source_id": "…", "snippet": "…", "origin": "stub" } ],
  "react_steps": [                       // ← ReAct trace UI 逐步畫「想→查→觀察」
    { "thought": "需要毛利率資料", "action": "search",
      "action_input": "台積電 毛利率", "observation": "取得引用：sid1" }
  ],
  "iterations": 3,
  "status": "answered",                  // answered / exhausted
  "compliance_status": "passed"
}
```

### (c) Alert Inbox（Watchdog 事件）
```jsonc
// 與 R3 約定的 WatchdogAlert（見 docs/R3_watchdog_開工指南.md §3）
{
  "event_id": "mops-2330-20260315-001",
  "stock_id": "2330",
  "summary": "事件合規判斷摘要（0 買賣建議）",
  "compliance_status": "passed",         // passed / blocked
  "evidence": [ { "source_id": "mops-2330-…", "snippet": "…", "origin": "news" } ],
  "severity": "info"                     // info / watch / alert
}
```

> 把這三段存成 `mocks/*.json`，UI 一律從 mock 讀；接真 API 時只換資料來源。

## 3. 最短路徑（5 個畫面）
1. **對話 + 引用 UI**（US1/SC-007）：輸入框 → 顯示 `answer` + 下方 `citations` 列表。
2. **Citation Tracer**：點一條 citation → 跳到/highlight 對應原文（用 `source_id` 對應；mock 階段先跳到 snippet 卡片，**跳轉正確率要 100%**）。
3. **Report Viewer + 匯出 PDF**：把 answer + citations 排成完整報告頁。
4. **Alert Inbox**：讀 (c) 的 WatchdogAlert 陣列，`severity` 上色、`compliance_status=blocked` 標紅。
5. **ReAct trace UI**：讀 (b) 的 `react_steps` 逐步畫「想→查→觀察」時間軸。

## 4. ⚠️ 後端接口依賴（要跟 R2 敲）
目前後端**沒有 HTTP API**，只有 CLI / Python 函式。要上線需要一支 **thin FastAPI**：
```
POST /ask        body {query}            → §2(a) JSON
POST /research   body {question}         → §2(b) JSON
GET  /alerts                             → §2(c) JSON 陣列
```
內部就是包 `build_workflow().invoke({"query": q})` / `run_deep_research(q)`。**誰寫先講好**（R2 owns 前後端接口；你也可自告奮勇寫，反正你最懂前端要什麼）。**在它出現前，你用 mock 全速開發。**

## 5. DoD（照順序勾）
- [ ] 技術選型拍板（Chainlit 核心 + Next.js Landing）
- [ ] `mocks/*.json` 依 §2 三契約建好
- [ ] 對話+引用 UI 跑通（讀 mock）
- [ ] Citation Tracer 點擊跳轉**正確率 100%**
- [ ] Alert Inbox + ReAct trace UI（讀 mock (c)/(b)）
- [ ] **手機 RWD 4 場景無跑版**（SC-005）
- [ ] 與 R2 接 thin API、換掉 mock
- [ ] **Vercel 部署 + Landing 上線**（W4，配 R1 文案）
- [ ] **Demo 備援影片定稿 + 斷網切換演練過**（憲法 V）

## 6. 防雷
- **斷網要能切備援**（憲法 V）：UI 要支援「讀本地 mock / 預錄影片」當 Plan B，Demo Day 現場切換**先演練**。
- **引用是門面**：每句結論都要點得到來源（SC-007）；mock 階段就把「點 citation→跳原文」做對。
- **契約別自己發明**：§2 欄位名要跟後端**一字不差**（`source_id`/`compliance_status`/`react_steps`…），否則接真 API 要重工。改契約 = R2/R3/R7 一起改。
- **Alert / trace 先用 mock**：Watchdog（R3 W3）、Deep Research 真 trace 較晚才有 → 你先用 §2(b)(c) 的 mock JSON，後端就緒再換。
- 卡住找誰：JSON 契約 / thin API → R2（施惠棋）；Watchdog 事件格式 → R3（謝劼恩）；4 場景畫面 / 文案 → R1（郝家銘）；離線備援資料 / mock trace → R4（吳瑾瑜）。

## 7. 一天開工順序（建議）
1. 上午：選型拍板 → 起 Chainlit（或 Next.js）骨架、能開頁面、輸入框能送出。
2. 中午：依 §2(a) mock 把「答案 + 引用列表」畫出來。
3. 下午：Citation Tracer 點擊跳轉 + Alert Inbox（mock (c)）。
4. 收工前：手機 RWD 掃一遍、把 §2 三個 mock 收進 `mocks/`，跟 R2 約 thin API 時程。
