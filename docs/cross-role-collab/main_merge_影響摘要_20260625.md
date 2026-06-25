# Main Merge 影響摘要

> 合併日期：2026-06-25  
> 合併至：`frontend_2026_0622`  
> 涵蓋 commits：從 `c93ff4e`（上次 merge）到 `8a39097`（本次 HEAD）

---

## 一、各角色改動速覽

| Commit | 角色 | 改動 | 影響範圍 |
|---|---|---|---|
| `abb4988` | **R2** | `graph/nodes/visual_reader.py` 新增 Phase B 查詢期 vision 讀圖節點 | R7 型別、R3 workflow 架構 |
| `8a39097` | **R4** | ingestion 垃圾 chunk 過濾（24% = 1191 筆清掉）| R3 retrieval 品質、R5 eval |
| `5b76774` | **R5** | eval runner 場景 3 退役 ColPali dispatch → text workflow | R5 eval 結構 |
| `1214974` `65716fd` | **R7+R3** | peer-compare 完整串接（PR #27）| 已完成 |
| `365a2fc` | **R2** | `docs/architecture.md` 新增 7 張 Mermaid 架構圖 | 全員參考 |

---

## 二、R7 需要處理的改動

### ⚠️ 已修正：`CitationOrigin` 缺 `'vision'`

**問題**：`graph/state.py`（backend）的 `CitationOrigin` 在 `abb4988` 加入了 `"vision"`，  
但前端 `types/api.ts` 沒有同步更新：

```typescript
// 修正前（缺 vision）
export type CitationOrigin = "stub" | "bm25" | "embedding" | "colpali" | "rerank" | "news";

// 修正後
export type CitationOrigin = "stub" | "bm25" | "embedding" | "colpali" | "rerank" | "news" | "vision";
```

**影響**：`adapters.ts` 的 `retrieval_degraded` 計算只判斷 `bm25` 和 `stub`，`vision` origin 不受影響。  
但若其他地方有 `switch/exhaustive check`，`"vision"` 會落入預設分支導致靜默錯誤。  
→ **已在本次 merge 修正。**

### ✅ peer-compare 串接完成，不需額外處理

PR #27 已 merge，以下功能全上線：
- `api.peerCompare()` 呼叫真實 `POST /peer-compare`
- `peer/page.tsx` 全部顯示真實 response（KPI、財務、法說、趨勢、摘要）
- `lib/peer-result.ts` 新增 `normalizePeerCompare()` normalizer
- 引用追蹤器顯示 peer citations，點擊走 `/chunk`
- `compliance_status` 顯示於 ComplianceBanner

**R7 任務清單更新**：`POST /peer-compare` 串接視為完成，可從待辦移除。

---

## 三、R3 需要知道的改動

### visual_reader 新節點（Phase B）

`workflow.py` 在 retriever 後加入 `visual_reader` 節點：

```
Planner → Retriever → [visual_reader] → Calculator → Writer → Compliance
```

**設計**：
- 預設 **關閉**（`VISUAL_READER=1` 才啟用）
- 觸發條件：看圖題且全脈絡無數字
- 失敗 no-op：任何外呼失敗不影響主流程
- 產生 `origin="vision"` 的 citations

**R3 架構圖需更新**：[R3_CTO_架構審查_20260625.md](R3_CTO_架構審查_20260625.md) 裡的 workflow 圖少了這個節點。

**R3 `_result_to_citation()` 白名單**：  
目前 `retriever.py` 的白名單：
```python
allowed_origins = {"stub", "bm25", "embedding", "colpali", "rerank", "news"}
```
`"vision"` 不在其中，visual_reader 的 citations 若流進 retriever 路徑會被 fallback 成 `"bm25"`。  
→ visual_reader 是 workflow 層節點（不走 retriever），此處影響有限，但建議補上以防萬一。

### ingestion 垃圾 chunk 清除

`is_low_information()` 過濾器上線：只含分隔符/標點/空白的 chunk 拒絕入庫。

**直接效益**：
- dev dataset 清除 1,191 筆垃圾 chunk（24%）
- 2882 國泰金的 chunk 品質從 73% 是虛線恢復正常
- vector search 命中真實內容的比例上升
- BM25 stub corpus 若改為從 BQ 載入（見 [R3_模組化改善方向](R3_模組化改善方向_20260625.md)），現在載到的也是乾淨資料

---

## 四、R5 需要知道的改動

### 場景 3 eval dispatch 調整

ColPali 從 eval dispatch 退役，場景 3（圖表題）改走 5 節點 text workflow：

```python
# 改前（eval/runner.py）
_DISPATCH = {
    "2": _run_deep_research,
    "3": _run_visual,         # ← 已移除
}

# 改後：場景 3 落入預設 _run_workflow（text workflow）
_DISPATCH = {
    "2": _run_deep_research,
}
```

**影響 R5 eval**：
- 場景 3 的 `contexts` 現在來自 Vision-OCR 入庫後的文字 chunks，而非 ColPali 視覺路
- Vision-OCR 已把圖表數值入庫，場景 3 應可正常取得 contexts
- Smoke test 的 `contexts_nonempty` check 對場景 3 的行為更嚴格（不再靠 ColPali 降級）

### ingestion 品質提升對 eval 的影響

垃圾 chunk 清除後，R5 的 Ragas 評分理論上會提升（contexts 品質更好）。  
建議重跑一次 baseline eval，取得清除垃圾後的新基準線。

---

## 五、全員參考：`docs/architecture.md`

新增 7 張 Mermaid 架構圖：
- 模組依賴分層圖
- 系統全貌（含 visual_reader Phase B）
- Ingestion 流程（含 Vision-OCR）
- RAG 3 路檢索
- LangGraph workflow + Deep Research agent
- 通知 7 關
- 使用者操作流程

位置：`docs/architecture.md`。建議各角色在設計跨元件功能前先參考。

---

## 六、行動項目彙整

| 角色 | 項目 | 狀態 |
|---|---|---|
| **R7** | `CitationOrigin` 加 `'vision'` | ✅ 已修正（本次 merge）|
| **R7** | peer-compare 串接 | ✅ PR #27 已完成 |
| **R3** | `_result_to_citation()` 白名單加 `'vision'` | 🔲 建議補上 |
| **R3** | 架構圖更新（加 visual_reader 節點）| 🔲 文件更新 |
| **R5** | 重跑 eval baseline（垃圾 chunk 清除後）| 🔲 建議執行 |
| **全員** | 參考 `docs/architecture.md` | 🔲 閱讀 |
