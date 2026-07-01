# Issue #78 inline 引用標記格式不一致 — R7 排查紀錄（2026-07-01）

**負責人**：R7（前端）
**日期**：2026-07-01
**分類**：前端防禦性修復 + 後端 prompt 待辦（issue #78，指派 wshc125）
**相關 commit**：`fc1dce7`

## 背景

在 issue #77 的排查過程中，實測「營運重點摘要」發現每段內容後面常夾帶一段多餘文字，例如：

```
...抵銷了部分智慧型手機的季節性影響（source:2330-2025Q1-p011-c001）。
```

這是 writer/ReAct agent 產生 `final_answer` 時自己夾帶的 inline 引用標記（設計上是給前端拿去精準對回 citation 用的），但這段標記文字從沒被從畫面顯示文字中移除，直接原封不動洩漏到 UI 上。

## 排查過程

### 第一輪：找到兩個問題疊在一起

1. **前端從沒清除標記**：`frontend/src/lib/adapters.ts` 的 `normalizeResearch()` / `normalizeAsk()` 只用標記做 `findInlineCitation()` 比對，取得 citation 後從未把標記本身從 `text` 欄位移除。
2. **正則比對不到當下格式**：負責解析的 `INLINE_SOURCE_RE` 只認 `source_id:` 或 `來源：`，但實測 LLM 吐出的是 `source:`（無 `_id`），完全比對不到：

   ```js
   "（source:2330-2025Q1-p011-c001）".match(INLINE_SOURCE_RE)  →  null
   ```

### 第二輪：格式持續冒出新變體

修好前兩種格式後，重新用真實瀏覽器操作（`preview_click` 真實點擊，非合成事件）反覆測試「台積電」相關問題，陸續又發現：

- **裸 ID（完全無前綴）**：`(43c7d7e7-d97d-4c06-a8c6-15acd9171eb6)`、`(dca4f820-87c5-4263-be74-b3af858c839d)`
- **方括號 + source_id**：`[source_id:2330-2024Q4-p012-c001,43c7d7e7-d97d-4c06-a8c6-15acd9171eb6]`

累計觀察到至少 **4 種格式**，幾乎每測一次同類問題就冒出新變體。

### 根因定位：前端 or 後端？

追到 `src/polaris/graph/prompts.py` 的 `GROUNDING_CLAUSE`（`/research` 端點的 `WRITER_SYSTEM_PROMPT`、`REACT_SYSTEM_PROMPT` 都靠它接地）：

```python
GROUNDING_CLAUSE = (
    "每個關鍵數字或主張都要標註對應來源（source_id）；"
    "找不到依據就明說資料不足，不得臆測。"
)
```

只要求「標註來源」，**沒有規定輸出成什麼固定格式**（沒有具體範例）。對照同檔案的 `SYNTHESIS_SYSTEM_PROMPT` / `PEER_SYNTHESIS_SYSTEM_PROMPT`：這兩個有把格式寫死——「每個論點必須保留原有『（來源：sid）』標記」——實測沒有格式不一致的問題。

**結論：根因在後端 prompt（`GROUNDING_CLAUSE` 缺格式鎖定），不是前端解析能力不足。** 前端追新格式永遠是治標，只要 prompt 不鎖死格式，下一次生成就可能冒出第 5、第 6 種寫法。

## 已完成（R7 / 前端側，防禦性修復，非治本）

commit `fc1dce7`（`frontend/src/lib/adapters.ts`）：

1. `INLINE_SOURCE_RE` 同時支援括號 `()`/`（）` 與方括號 `[]`，前綴支援 `source_id` / `source` / `來源`
2. 新增保守版裸 ID 偵測 `BARE_ID_RE`：只在括號/方括號內容**整段**都長得像已知 id 格式（UUID / `ticker-yyyyQn-p頁-c塊` / `news_<hex>`）才視為標記，避免誤吃一般中文句子裡的括號附註（單位、英文縮寫、百分比等）——8 組正反測試案例全過
3. 新增 `stripInlineSource()`，對回 citation 後把標記從顯示文字中移除

已用真實瀏覽器操作（非合成事件）重新驗證多次，摘要文字不再出現原始標記。

## 待辦（R2，issue #78）

已開 [issue #78](https://github.com/holajennytw/polaris-desk/issues/78) 指派給 wshc125，附上 4 種格式範例與根因分析，建議把 `GROUNDING_CLAUSE` 比照 `SYNTHESIS_SYSTEM_PROMPT` 的做法鎖死成固定格式（例如統一「（來源：sid）」）。是否調整、調整成什麼格式，決定權在 R2。

## 相關 commit / issue

- `fc1dce7` fix(web): 清除摘要文字裡殘留的 inline 來源標記
- issue #78（本篇對應的後端待辦）
- issue #77（跨公司檢索污染，不同根因，另案處理中）
