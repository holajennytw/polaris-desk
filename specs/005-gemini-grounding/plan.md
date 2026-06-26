# Implementation Plan: Gemini 接地觸點（P0 + P1）

**Branch**: `005-gemini-grounding` | **Date**: 2026-06-26 | **Spec**: [spec.md](./spec.md)

---

## Summary

在 Deep Research 收尾（P0）與 peer-compare（P1）兩個面向使用者的出口，疊加 Gemini Flash 潤飾層。P0 同時產出兩個可重用純函式（`is_traceable_prose` + `numbers_grounded`）讓 P1 直接 import。所有路徑都有確定性 fallback，flag 關 → CI token=0、行為 byte-identical。

---

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: `google-genai` 新 SDK、LangGraph、pydantic  
**Storage**: N/A（純邏輯層，不動 BigQuery / pgvector）  
**Testing**: pytest（TDD；flag 關回歸 + 無金鑰 token=0 + fake client）  
**Target Platform**: Cloud Run（與本地 dev 相同）  
**Project Type**: Library / service layer  
**Performance Goals**: synthesis timeout < 8s（超時退 fallback）  
**Constraints**: flag 關 = token=0；不改現有函式簽名  
**Scale/Scope**: 兩個 API 端點（`/research`、`/peer-compare`）

---

## Constitution Check

| 憲法條款 | 檢查結果 |
|---------|---------|
| §I NFR-031 買賣建議 | ✅ 三條款 prompt + compliance 雙層防線；P1 R7 比較式紅隊題 Q131–Q134（v1）|
| §II 引用接地 | ✅ 閘門純函式（is_traceable_prose + numbers_grounded）結構驗證 |
| §IV Eval 品質門 | ✅ prose faithfulness 題 Q136–Q139（敘事接地，`gate_subset=prose_faithfulness`）已補；P1 peer 路徑（場景 5）Q135 已通；題庫＝R5 canonical v1 |
| §VI 技術棧 | ✅ `google-genai` 新 SDK + Gemini Flash |

---

## Project Structure

```text
specs/005-gemini-grounding/
├── spec.md
├── plan.md            # 本檔
├── research.md        # Phase 0（下方）
└── tasks.md           # /speckit-tasks 產出
```

主要改動檔案：

```text
src/polaris/graph/deep_research/
├── state.py           # + is_traceable_prose, numbers_grounded（純函式）
└── agent.py           # + _polish_synthesize（flag-gated LLM 潤飾）

src/polaris/
└── api.py             # + _peer_synthesis（flag-gated，P1）

tests/
├── unit/graph/deep_research/test_state_gates.py   # 新（純函式 TDD）
└── unit/graph/deep_research/test_polish_synth.py  # 新（P0 TDD）
└── unit/test_peer_synthesis.py                     # 新（P1 TDD）
```

---

## Phase 0 Research

### 決策 1：`is_traceable_prose` 設計

**現況**：`state.py` 已有 `is_fully_traceable`（bullet 格式，`- ` 開頭行才驗）。  
**問題**：Gemini 潤飾後的 prose 不一定是 bullet，`is_fully_traceable` 會全 False。  
**決策**：新增 `is_traceable_prose(text, evidence)` — 改為掃所有「（來源：sid）」出現位置，只要 ≥1 個 sid ∈ evidence 就 pass（prose 的結構比 bullet 鬆）。  
**理由**：prose 本來就是自由文，不能要求每句都有 tag，只需至少一個有效引用佐證。  
**替代方案**：語意閘門（侯補，P2）。

### 決策 2：`numbers_grounded` 設計

**決策**：用正則從 prose 抽所有數字 token（含 %、億、兆、pp 等單位），再從 evidence snippets 的去 source-tag 版本抽相同 pattern；若 prose 無數字 → True（無數字可驗）；有數字則需全部能在 evidence 中找到。  
**Why 先移 source-tag**：sid 如 `stub-2330` 含「2330」，不移除會把 sid 片段當有效數字來源（R3 風險）。  
**正規化**：中文數字（一千兩百）、全形數字、億/兆單位、pp 皆正規化後比對（R9 風險）。

### 決策 3：Synthesis prompt 結構

```python
SYNTHESIS_SYSTEM = (
    GROUNDING_CLAUSE + "\n" + NO_ADVICE_CLAUSE + "\n" + UNTRUSTED_CONTENT_CLAUSE + "\n"
    "規則：只把下方條列改寫成流暢敘事段落。不得新增原文未有的事實或數字。"
    "每個論點保留原有「（來源：sid）」標記。以繁體中文輸出。"
)
```

User prompt = 原 `_synthesize` 輸出的 bullet 條列（base）。

### 決策 4：Outcome logging 七種狀態

```python
# outcome 值（記 logger.info("deep_research.synthesis outcome=%s", outcome)）
OUTCOME_POLISHED           = "polished"        # LLM 潤飾 + 兩閘門通過
OUTCOME_GATE_TRACEABLE     = "gate_traceable"  # is_traceable_prose fail
OUTCOME_GATE_NUMBERS       = "gate_numbers"    # numbers_grounded fail
OUTCOME_LLM_ERROR          = "llm_error"       # LLM 呼叫丟例外
OUTCOME_NO_KEY             = "no_key"          # client is None
OUTCOME_COMPLIANCE_REJECT  = "compliance_rejected"  # P1 compliance fail
OUTCOME_FALLBACK           = "fallback"        # 其他原因退回
```

### 決策 5：Timeout 策略

synthesis 呼叫用 `call_with_retry` 現有機制（含 backoff）+ 最外層 try/except；超時例外歸 `OUTCOME_LLM_ERROR` → fallback。不加 asyncio.timeout（避免改 sync call chain）。

---

## Phase 1 Design — Data Model & Contracts

### 新增純函式（`state.py`）

```python
def is_traceable_prose(text: str, evidence: Sequence[Citation]) -> bool:
    """prose 中 ≥1 個「（來源：sid）」的 sid ∈ evidence。"""

def numbers_grounded(text: str, evidence: Sequence[Citation]) -> bool:
    """prose 中所有數字 token 都能在 evidence snippets（去 source-tag）中找到。"""
```

### P0 新增函式（`agent.py`）

```python
def _polish_synthesize(
    question: str,
    base: str,
    evidence: Sequence[Citation],
    *,
    client,
) -> tuple[str, str]:  # (output_text, outcome)
    """嘗試 LLM 潤飾；不過閘門 / 例外 → 回 (base, outcome)。"""
```

呼叫點：在 `run_deep_research` 確定性 `_synthesize` 產出 `base` 後，若 `DEEP_RESEARCH_LLM_SYNTHESIS` 且 client 有金鑰，叫 `_polish_synthesize`。

### P1 新增函式（`api.py`）

```python
def _peer_synthesis(
    base_summary: str,
    citations: list[str],  # 已接地的比較列
    *,
    client,
) -> tuple[str, str]:  # (summary_text, outcome)
    """嘗試 Gemini 潤飾 peer-compare 比較結論；不過 → 回 (base_summary, fallback)。"""
```

呼叫點：`peer_compare` 組好 `raw_summary` 後，若 `PEER_COMPARE_LLM_SYNTHESIS`，呼叫 `_peer_synthesis`，最後再過 `compliance_agent.review`。

### API 契約（對外行為不變）

`/research` 與 `/peer-compare` 的 response schema 不變（`final_answer`/`summary` 欄位型別不變），僅內容從 bullet → prose（flag 開時）。

---

## TDD Tasks（實作順序）

### Task 1 — 純函式 TDD（`state.py`）

測試先行，純函式後寫。

**測試場景**（`test_state_gates.py`）：

```
is_traceable_prose:
- [pass] prose 含 ≥1 個有效 (來源：sid) → True
- [fail] prose 無任何 (來源：...) → False
- [fail] sid 不在 evidence → False
- [edge] 半形括號 (來源：sid) → True（正規化）

numbers_grounded:
- [pass] prose 無數字 → True
- [pass] 數字在 evidence snippet → True
- [fail] 數字不在 evidence → False
- [edge] sid 含數字（如 stub-2330）→ 不算在 evidence 數字，prose 有 2330 → False
- [edge] 中文「一千兩百萬」 → 正規化後 1200 萬可比對
- [edge] 百分比 12.3% → 抽 12.3
- [edge] pp → 抽前面數字
```

### Task 2 — `_polish_synthesize` TDD（`agent.py`）

```
- flag=0 → 直接回 base（不呼叫 LLM）
- flag=1, no client → outcome=no_key, 回 base
- flag=1, fake client 回含正確 (來源：sid) prose → outcome=polished
- flag=1, fake client 回不含引用 prose → outcome=gate_traceable, 回 base
- flag=1, fake client 回含幻覺數字 → outcome=gate_numbers, 回 base
- flag=1, client.generate 丟例外 → outcome=llm_error, 回 base
```

### Task 3 — `run_deep_research` 整合（`agent.py`）

- flag=0：整條路徑 byte-identical（回歸）
- flag=1, stub client：polish 被呼叫 1 次

### Task 4 — `_peer_synthesis` TDD（`api.py`）

```
- flag=0 → raw_summary 不變
- flag=1, fake client, 過閘 + 過 compliance → outcome=polished
- flag=1, LLM prose 含買賣建議 → compliance_rejected, 回 raw_summary
- flag=1, 閘門 fail → fallback
```

### Task 5 — eval 題補充

- P0：在 R5 canonical `questions_v1.csv` 補 prose faithfulness 場景 Q136–Q139（敘事流暢且引用正確）
- P1：讓 eval runner 能路由 `/peer-compare`；確認正向 peer 題 Q135（場景 5）跑的是 peer 路徑

### Task 6 — Outcome logging + 採用率

- `grep "deep_research.synthesis outcome="` 在 prod 可統計 polished vs fallback 比例
- Cloud Run log filter 驗收

---

## Deployment Checklist

- [ ] `DEEP_RESEARCH_LLM_SYNTHESIS=0`（prod 預設，先上後開 flag）
- [ ] `PEER_COMPARE_LLM_SYNTHESIS=0`（同上）
- [ ] `SUGGESTIONS_LLM=0`（P3 預設關，同先上後開）
- [ ] Cloud Run 環境變數確認有 `GEMINI_API_KEY`（Secret Manager 已有）
- [ ] eval 跑比較式紅隊 Q131–Q134 + 正向 Q135（peer compliance），全 0 買賣建議才開 P1 flag
- [x] prose faithfulness 題 Q136–Q139 已補（題庫遷至 R5 v1），全套測試綠（§IV 品質門）
- [ ] prod 觀察 `outcome=polished` 採用率 ≥ 50% 才算有效上線

### Flag 開啟順序（分批，**不要三個一起開**）

風險不同，分批 canary：

1. **P3**（`SUGGESTIONS_LLM`）— 最低風險（不接地、僅 compliance）。第一個試水溫。
2. **P0**（`DEEP_RESEARCH_LLM_SYNTHESIS`）— 已實測 `polished`。觀察 P3 的 `outcome` log 約一天後再開。
3. **P1**（`PEER_COMPARE_LLM_SYNTHESIS`）— 受紅隊 eval 卡關，且依設計大多退回 fallback（見下方 §P1 決議）。CP 值最低，**最後開**、或先不開等派生數字決議。

### 採用率觀測（Cloud Run log filter）

部署後**實際拿來查**（別只寫在規格裡）。三個觸點各自的 `outcome` 都進 structured log：

```sh
# 採用率（polished/llm 佔比）— 三個觸點各跑一次
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=polaris-api
   AND textPayload:"deep_research.synthesis outcome="' \
  --project <PROJECT> --freshness=1d --format='value(textPayload)' \
  | sort | uniq -c | sort -rn
# P1：textPayload:"peer_synthesis outcome="；P3：textPayload:"llm_suggestions outcome="
```

`outcome=polished`（P0）/ `llm`（P3）佔比即採用率；P1 `gate_failed` 佔比高屬**預期**（見 §P1 決議）。

---

## 風險對照（出自決策選單 §5）

| 風險 | 緩解（本 spec 負責） |
|------|---------------------|
| R1 語意幻覺（tag 在語意錯）| 人工抽樣 + 語意 judge（P2 後補），本次做結構閘門 |
| R2 閘門太嚴靜默 fallback | Task 6 outcome logging + 採用率指標 |
| R3 sid 數字誤算 | `numbers_grounded` 先移 source-tag（Task 1） |
| R7 peer 比較→買賣 | compliance 雙層；Q131–Q135 eval 過才開 flag |
| R9 數字格式 | `numbers_grounded` 正規化單位（Task 1） |
| R10 共用函式回歸 | flag 關 byte-identical 回歸測試（Task 2/3） |
| R11 無 eval 門檻 | Task 5 補 eval 題，過才開 flag |
| R12 跨模組耦合 | 閘門在 `deep_research.state`，P1 import；不改簽名 |
