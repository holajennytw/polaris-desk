# Gemini 接地觸點 — 全專案盤點與決策選單

> **目的**：列出全專案「可以做接地 Gemini 生成」的觸點，附現況、效益、工數、風險，**讓團隊成員勾選要做哪些**。
> **盤點方法**：`grep active_llm / .generate / *_SYSTEM_PROMPT` 全專案 LLM 觸點，依「是否面向使用者輸出事實/數字 × 是否已接地」分四類。
> **日期**：2026-06-25　**狀態**：決策用　**相關**：[Deep Research 收尾接地設計](superpowers/specs/2026-06-25-deep-research-gemini-synthesis-design.md)、[實作計畫](superpowers/plans/2026-06-25-deep-research-gemini-synthesis.md)

---

## 0. 一句話判斷原則

> **凡「面向使用者、輸出事實或數字」的出口 → 必須接地 Gemini；內部推理 / 偵測 / 嵌入 → 不需要。**

「接地 Gemini」的共同模式（憲法 §II 引用接地 + §I NFR-031）：

```
GROUNDING_CLAUSE + NO_ADVICE_CLAUSE + UNTRUSTED_CONTENT_CLAUSE   ← 三條款（prompts.py 既有）
  + 引用接地（每句結論帶（來源：sid））
  + 驗證閘門（is_traceable_prose + numbers_grounded）            ← 本案 P0 產出的純函式，可重用
  + 確定性 fallback（不過閘門 / 無金鑰 → 退回確定性，最差 = 現狀）
```

---

## 1. 決策選單（team 勾選用）

| 觸點 | 面向使用者 | 現況 | 接地後得到 | 工數 | 風險（碼見 §5）| 建議 | ☐ 決定 |
|---|---|---|---|---|---|---|---|
| **Deep Research 收尾** `/research` | ✅ | 確定性條列 | 流暢帶引用結論 | 中 | 中：R1 語意幻覺 · R4 延遲 · R11 無評測 | **P0 — 進行中（本案）** | ☐ |
| **同業比較** `/peer-compare` | ✅ | 結構化表+引用、**無敘事** | 「誰較強、差異原因」敘事結論 | **低**（重用 P0 閘門）| 中：**R7 比較→暗示買賣** · R1 | **P1 — 推薦下一個** | ☐ |
| **矛盾偵測** `/contradiction` summary | ✅ | 模板字串 | 矛盾的白話說明 | 低 | 低：R1 · R2 | P2（選配，YAGNI 暫緩）| ☐ |
| **每日簡報** `daily_status` 角色摘要 | ✅ | 模板字串 | 角色化自然語摘要 | 中 | 中–高：**R5 成本** · R10 回歸 | ~~P2（選配）~~ → ❌ **不做**（token 成本不划算，維持模板）| ☒ |
| **提示問句** `/suggestions` | ✅ | 規則式精選 | LLM 動態問句 | 低 | 低–中：**R7 問句暗示買賣** | **P3 — ✅ 已落地**（免接地 + compliance 守門，flag `SUGGESTIONS_LLM`，預設關）| ☑ |

> P0 已有設計+計畫；其餘等團隊勾選。**最划算的是 P1**，但注意它的 **R7（比較被當買賣建議）比 Deep Research 更尖銳** —— 詳見 §5。**決策前務必讀 §5 風險清單。**

---

## 2. 已接地 —— 維持，當樣板（A 類，不用動）

這些已是「smart 生成 + 確定性 fallback」的正確形狀，新觸點照抄即可：

| 觸點 | 出口 | prompt | 接地狀態 |
|---|---|---|---|
| `writer_agent.make_draft` | `/ask` | `WRITER_SYSTEM_PROMPT` | ✅ 引用 + 三條款 + fallback |
| `watchdog._smart_summary` | `/alerts` | `WATCHDOG_SYSTEM_PROMPT` | ✅ `_build_evidence` 引用 + 三條款 + `_fallback_summary` |
| `news/card` | 新聞卡 | `NEWS_CARD_SYSTEM_PROMPT` | ✅ 三條款 + fallback |

> **`watchdog` 的「`_smart_summary` 走 LLM、失敗退 `_fallback_summary`」就是本案要套到 Deep Research 的同一形狀** —— 想理解模式先讀 [watchdog/agent.py](../src/polaris/graph/watchdog/agent.py)。

---

## 3. 是 LLM、但不需要接地（B 類，別誤加）

| 觸點 | 用途 | 為何免接地 |
|---|---|---|
| `planner_agent.make_plan` | 把問句拆成檢索步驟 | 內部推理，不輸出事實/數字給使用者 |
| `compliance_agent.review` | 偵測買賣建議 | 偵測（非生成），本身就是守門 |
| `deep_research._decide` | 驅動 ReAct 檢索決策 | 決策非最終文字（已帶 `REACT_SYSTEM_PROMPT` 三條款）|
| ingestion `active_llm().embed` | 產生 768 維向量 | 嵌入非文字生成 |

> 對這些加「引用接地」是**白工且可能有害**（內部推理被迫掛來源會降低品質）。

---

## 4. 候選詳述（team 評估用）

### P1 — `/peer-compare` 敘事結論（推薦）

- **現況**：[api.py:748](../src/polaris/api.py) `peer_compare` 從結構化財報表（`list_financials`）取兩家 KPI，組成帶引用的比較列，`summary` 是**確定性模板字串**（`{label}：A v（來源 src）vs B v（來源 src）`）。無「孰優孰劣、差異原因」的敘事。
- **接地後**：在已接地的比較列上，用 Gemini 生成一段「台積電毛利率較聯發科高 X pp，主因…（來源：…）」的結論。
- **工數低**：資料已接地、已有 `citations`，**直接重用本案 `is_traceable_prose` / `numbers_grounded` / 降級矩陣**，只需新增一個 `_peer_synthesis_prompt` + 一個 flag。
- **風險低**：數字全來自結構化表（白名單明確），閘門比 Deep Research 更好守。
- **依賴**：本案 P0 先把閘門純函式落地（`state.py`），P1 import 即用。
- **⚠️ 實測（2026-06-26，真 Flash 免費配額）**：P1 潤飾**幾乎必退回 fallback**。原因：比較敘事天生會算「高出 X 個百分點」這種**派生數字**（如 58.8−47.9=10.9），而 `numbers_grounded_in_text` 是嚴格子集檢查 → 派生數字不在 base → `gate_failed`。輸出本身流暢、句句帶來源、無買賣建議，但被閘門擋下。**團隊決議：維持嚴格閘門**（最壞 = 現狀確定性表，零幻覺風險），接受 P1 採用率低；prod `outcome=gate_failed` 佔比高屬**預期**、非故障。日後若要提高採用率，再評估「允許經驗證的接地算術（兩個 base 數字的差/和，且結果需等於精確值）」。P0 / P3 實測正常（`polished` / `llm`）。

### P2 — `/contradiction` summary（選配）

- **現況**：[api.py:279](../src/polaris/api.py) 用 `_has_provable_conflict`（數字 token 互斥檢查）+ 固定模板句（「本次 KPI 與摘要未發現…可證明的矛盾」）。
- **接地後**：把「哪裡矛盾、誰對誰」講成白話。
- **評估**：目前確定性即安全且可讀，**效益/風險偏低，YAGNI 暫緩**；要做也是重用同閘門。

### P2 — `daily_status` 角色摘要（選配）

- **現況**：[daily_status/render.py](../src/polaris/daily_status/render.py) `render_day_block` / `render_csv` 全模板，無 LLM。
- **接地後**：7 角色各自的自然語日報。
- **評估**：量大（多角色×每日）、token 成本要先估；中等風險。
- **決定（2026-06-26）**：❌ **不做** —— 跑量大、token 不划算，維持確定性模板日報即可。

### P3 — `/suggestions` 動態問句（免接地）

- **現況**：[api.py:267](../src/polaris/api.py) 規則式精選，回應已留 `source: "llm"` 擴充位、`is_generating` 旗標。
- **特別**：若改 LLM 生成提示問句，**只需 `NO_ADVICE_CLAUSE`（不可暗示買賣），不需 grounding** —— 問句不含事實/數字，無來源可接。歸在這裡是提醒「別過度套接地模式」。

---

## 5. 風險清單（決策必讀）

### 5.1 跨觸點共通風險

| 碼 | 風險 | 影響觸點 | 後果 | 緩解 |
|---|---|---|---|---|
| **R1** | **結構接地 ≠ 語意接地**：句子帶了`（來源：sid）`，但該主張其實不在那則來源（張冠李戴）| 全部 | 看似有出處實則幻覺，**過得了閘門**（閘門只驗結構+數字，不驗語意）| 上線先小流量 + 人工抽樣校；P2 再加「句↔來源」語意比對 LLM judge；保留 react_steps 供稽核 |
| **R2** | **閘門過嚴 → 功能幾乎不啟動**：Flash 用半形 `(來源: s1)` 或改寫掉 tag → 一律 fail → 永遠退回 base | 全部 | 花了工、prod 卻一直走確定性，**看似上線實則沒效** | ✅ **已落地**：P0 plan Task 6 每分支記 `deep_research.synthesis outcome=`，prod grep 算 polished vs fallback 採用率；✅ 半/全形括號＋冒號皆收（`_SOURCE_TAG` `[（(]來源[：:]…`，回歸測試 `test_half_width_colon_normalized`）|
| **R3** | **閘門過寬**：數字抽取沒排除 sid 內數字（如 `stub-2330` 的 2330）| 全部 | 幻覺數字若巧合等於某 sid 片段 → 假性過關 | 抽數字前先 `_SOURCE_TAG.sub("",…)`（已列入本案 plan I2）|
| **R4** | **延遲疊加 / Gemini 慢**：收尾多一次 round-trip 疊在 ≤6 輪 ReAct + compliance 上 | /research /peer | 同步端點下**使用者等到 timeout** | 潤飾設較短 timeout、逾時退 base；評估非同步 / 串流 |
| **R5** | **Token 成本失控** | **daily_status 尤甚**（角色×每日）| 燒錢、觸發 `BudgetExceeded` | 先估量再做；`llm/budget.py` 護欄；daily 走 batch + 快取 |
| **R6** | **靜默退回不可觀測**：`except Exception` 吞掉 LLM 失敗 | 全部 | 線上分不出「沒開 flag」與「一直在退回」| ✅ **已落地**：同 R2，`outcome=llm_error/gate_failed/...` 七種狀態日誌（P0 plan Task 6）|
| **R8** | **Prompt injection**：來源片段含惡意指令（新聞尤甚）| news/card /research /peer | 被誘導越線或亂引用 | `UNTRUSTED_CONTENT_CLAUSE` 已防（主防線）；不可信來源（新聞）再加來源白名單 |
| **R9** | **數字/語言格式遺漏**：中文數字（一千兩百）、全形數字、億/兆單位、pp vs % | 全部 | 漏抽→假過；誤抽→假退 | 正規化單位；測中文數字；pp 與 % 分開比對 |
| **R10** | **共用函式回歸**：動到 `_synthesize` / `compliance_agent` 會牽連 /ask、/alerts | 全部 | 改一處壞多端點 | 全套回歸測；flag 隔離；**不改既有簽名** |
| **R11** | **無評測門檻**：新敘事沒進 Ragas / G3，prose faithfulness 沒被量測 | 全部 | 未驗證就上 prod | 上 prod 前補 eval 題；CP / Faithfulness gate 過了才開 flag |
| **R12** | **跨模組耦合**：P1/P2 直接 import `deep_research.state` 的閘門 | P1/P2 | P0 改閘門簽名 → 連坐壞 | 閘門抽到 shared 模組；簽名凍結 + 共用測試 |
| **R13** | **flag 擴散 / prod 設定漂移**：每個觸點一個 flag（回想 CORS 雙別名、traffic-pin 坑）| 全部 | 多 flag 難管、開錯/沒開 | 集中於本文件記錄；部署 checklist 逐項確認 |

### 5.2 各觸點特有風險

- **`/peer-compare`（R7，最該注意）**：比較天生靠近買賣建議 —— Gemini 寫「台積電毛利率較聯發科高、體質更強」極易被讀成「買台積電」，**踩憲法 §I NFR-031**。確定性模板只列數字不下判斷，所以現在安全；一旦改 LLM 敘事，**compliance 必須能攔「比較式暗示買賣」**，prompt 要明禁「孰優孰劣導向買賣 / 推薦持有」。
  - ✅ **已補紅隊題**：eval 題庫 `questions_v0.csv` 新增 **Q076–Q080**（比較式誘導買賣，驗收 = 0 買賣關鍵字）。
  - ⚠️ **P1 前置（未做）**：eval runner 目前只路由 `場景2→deep_research`、其餘 `→app.invoke(/ask)`，**沒有跑 `/peer-compare` 路徑**；Q076–Q080 現在實際測的是 `/ask` 的 compliance。P1 實作時**必須**：(1) peer 敘事輸出過 `compliance_agent.review`；(2) 讓 eval runner 能跑 peer 路徑，這幾題才真正守在 peer-compare 上。compliance 過了才開 flag。
- **`/suggestions`（R7）**：LLM 生成的「提示問句」本身可能暗示買賣（如「該不該買 X」）→ 即使免 grounding，**仍需 `NO_ADVICE_CLAUSE` 過濾問句**。
- **`daily_status`（R5 + R10）**：7 角色 × 每日 = prompt 維護面大、token 量大；且 render 是多端點共用，回歸面廣。**先估成本與回歸範圍**再決定。
- **`/contradiction`（R1）**：矛盾敘事最怕「講錯誰跟誰矛盾」（語意接地問題），但量小、現況安全，YAGNI 暫緩風險可接受。

### 5.3 風險總結

> **最危險的不是「Gemini 亂講」（閘門+fallback 擋得住），而是兩件事**：
> **① R1 語意幻覺**（tag 在、語意錯，閘門看不出）→ 需人工抽樣 + 語意 judge；
> **② R2 靜默沒生效**（閘門太嚴一直 fallback）→ 需「採用率」指標，否則團隊以為做完了其實沒效。
> 兩者都**不是寫程式能單獨解決的，要配指標與抽樣**。R7（比較→買賣）是 peer-compare 的專屬紅線，開工前先補紅隊題。

---

## 6. 怎麼接（任一 C 類觸點的共同步驟）

1. 找到該出口「已接地的確定性資料」（peer-compare 的比較列 / contradiction 的 KPI 比對 / daily 的 digest）當 `base`。
2. 加 flag（`<FEATURE>_LLM_SYNTHESIS`，預設關，CI token=0）。
3. 寫 `_<feature>_synthesis_prompt(base)`，system prompt = 三條款 + 「只改寫 base、不新增事實、保留（來源：sid）」。
4. 生成後過 `is_traceable_prose` + `numbers_grounded`（**import 自 `deep_research.state`**，P0 產出）。
5. 不過 / 無金鑰 / 例外 → 退回 `base`。最後過 `compliance_agent.review`。
6. TDD：flag 關回歸（byte-identical）、無金鑰 token=0、fake client 驗潤飾與降級。

> P0 已把第 4 步做成可重用純函式 —— **這是先做 Deep Research 的槓桿：一次設計，P1/P2 共用閘門。**

---

## 7. 給團隊：請在 §1 表格「☐ 決定」欄勾選

- 想做 → 填認領人 + 目標週次；P1 可直接複用本案 PR 的閘門。
- 暫緩 → 標 YAGNI，日後有需求再起。
- 有疑問 → 標在該列，PR review 時討論（憲法 I/II/III 一律確認）。
