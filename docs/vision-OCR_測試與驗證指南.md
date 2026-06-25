# Vision-OCR Ingestion — 測試與驗證指南（給 R1 / R5 / R7 + agent）

> **這是什麼**：法說簡報的「圖表頁 / 掃描頁」原本文字 RAG 抓不到（0 文字層）。本功能在
> **入庫時**用 Gemini vision 把那些頁抽成結構化文字，併入既有 `chunks` → 文字 3 路 → `/ask`。
> 取代失敗的單向量 ColPali 第 4 路。設計：[`docs/superpowers/specs/2026-06-23-vision-ocr-to-text-ingestion-design.md`](superpowers/specs/2026-06-23-vision-ocr-to-text-ingestion-design.md)。
>
> **現況（2026-06-25）**：✅ **全量入庫完成** — dev dataset `polaris_dev_wayne.chunks` 已有
> **全 20 檔**中文法說簡報（清理後 **3622 塊** / 768 維，2025Q1–2026Q1）。
> 已做品質清理：移除 1191 塊純線條雜訊塊（`is_low_information` 源頭修掉，重跑不再生），
> 重複冗餘 1392→204，embedding 全 768 維非退化、最近鄰一致性 OK。`polaris_core` 未動。
> 分工 / 各檔塊數 / 清理細節見 [`vision-OCR_入庫分工.md`](vision-OCR_入庫分工.md)。各角色可全面測試。
>
> 標記：**🤖 = agent 可自動跑**；**🧑 = human 必做**（金鑰 / gcloud 登入，憲法：金鑰永不 commit）。

---

## 各角色起跑清單（先讀這段）

**大前提**：唯一硬性先後 = **R4 寫 `polaris_core` 要等 R1 Gate1 過**；其餘全部可並行。
行動細節見對應章節；總覽見 GitHub issue [holajennytw/polaris-desk#24](https://github.com/holajennytw/polaris-desk/issues/24)。

| 角色 | 現在可以做 | 章節 | 是否被 gate |
|------|-----------|------|------------|
| **R1**（Gate1，關鍵） | 全 20 檔 `data/vision_chunks/<ticker>_gate1.csv` 已產好，抽 20–30 頁 / ≥4 公司比對數字 **≥95%** 放行 | §1 | ⛔ 是放行者，不被 gate |
| **R5**（Gate2/eval） | 對 dev 跑檢索驗證 + 把 Ragas 指到 dev 跑圖表題集 | §3 | 🟢 現在可做 |
| **R7**（前端） | 指向 dev 起 API 問圖表題，確認 citation 帶頁碼；**零前端改動** | §4 | 🟢 現在可做 |
| **R4**（ingestion owner） | 審 code、把 fetch-skill 修補套上游 plugin repo、確認 `financial_statement` 來源 | §2 | 🟡 載 core 等 Gate1 |
| **R3**（檢索） | 待命，本案不動檢索端（無 code） | — | ⚪ 無事 |
| **PM** | 決定放大範圍（20 檔）、Vertex 配額策略（GA 模型 / 升級帳號脫離 trial） | — | — |

> **看 dev 目前有哪些資料可測**（隨全量 pilot 持續增加）：
> ```bash
> bq query --use_legacy_sql=false \
>  'SELECT ticker, COUNT(*) chunks, COUNT(DISTINCT fiscal_period) periods
>   FROM `polaris-desk-team.polaris_dev_wayne.chunks` GROUP BY ticker ORDER BY ticker'
> ```

---

## 0. 一眼確認「它在動」（最快 — 任何人都能跑）

vision chunk 已在 dev 庫，且檢索得到。**🤖 直接查 BigQuery：**

```bash
bq query --use_legacy_sql=false \
 'SELECT ticker, fiscal_period, chunk_id, ARRAY_LENGTH(embedding) dim, SUBSTR(chunk_text,0,40) preview
  FROM `polaris-desk-team.polaris_dev_wayne.chunks` ORDER BY chunk_id'
```

**預期輸出**：多列 vision chunk（隨全量 pilot 持續增加），每列 `dim=768`、`chunk_text` 是「頁摘要＋數字條列」。例：`2330-2025Q1-p004-c001` = 台積電綜合損益表頁。

**端到端檢索證據（已實測，2026-06-24）**——對 dev 庫提問，命中正確的 vision 頁：

| 提問 | 命中 chunk | 相似度 |
|---|---|---|
| 台積電 2025Q1 毛利率與營業收入 | `2330-2025Q1-p004-c001`（綜合損益表） | 0.817 |
| 中信金控 2025 第一季 ROE | `2891-2025Q1-p006-c001`（ROE 領先同業） | 0.854 |

要自己重現這段檢索，見 §3。

---

## 前置：環境與金鑰（🧑 一次性）

```bash
uv venv --python 3.13 && uv pip install -e ".[dev,vision]"   # vision extra = pymupdf 渲染
gcloud auth application-default login                          # 🧑 Vertex 生成走 ADC
```

**金鑰（embedding 恆需 `GEMINI_API_KEY`，即使生成走 Vertex）** 放在 Secret Manager，ADC 帳號可讀：

```bash
export GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=gemini-api-key --project=polaris-desk-team)
```

> ⚠️ 只在 shell export，**永不寫進檔案 / 永不 commit**（憲法 III）。無金鑰時 ingestion 的
> embedding 會停用並印提示（不會瞎產假向量）。

---

## 1. 🧑 R1 — Gate1（抽取準確率，放行的關鍵）

**R1 是唯一能放行 vision chunk 進 `polaris_core` 的品質關**（≥95% 數字準確率）。

```bash
export GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=gemini-api-key --project=polaris-desk-team)
export VISION_EXTRACTION=1 GEMINI_USE_VERTEX=1
uv run python scripts/vision_ingest_pilot.py --ticker 2330 --ticker 2891   # 不帶 --ingest = 只產 JSONL+Gate1
```

**產物**：`data/vision_chunks/<ticker>.jsonl` + `<ticker>_gate1.csv`（欄位 `pdf,page,extracted,text_preview`）。

**Gate1 做法**：抽 20–30 頁、≥4 公司、涵蓋 pie / trend / 財報表，**把 `text_preview` 的數字逐一對原 PDF 頁**，
數字準確率 **≥95%** 才放行。`extracted=FAIL` 的頁代表抽取失敗（誠實空白、未入庫，不算幻覺）。

> 全量 346 頁因 `gemini-3-preview` 的 Vertex QPM 限流是長時工作（已內建 `--throttle` 預設 3s 自我節流 +
> 逐 PDF 落地，中斷不丟前面成果）。先抽樣即可放行；放大全量留給背景批次。

**Gate1 通過 → 通知 R4 載入 `polaris_core`。**

---

## 2. 🧑 R4 — 載入 canonical（憲法 III：唯一可寫 core 的角色）

過 Gate1 後，**用 R4 帳號（holajennytw）或 R4 GCE SA + `BQ_ALLOW_CORE_WRITE=1`**：

```bash
export GEMINI_API_KEY=... VISION_EXTRACTION=1 GEMINI_USE_VERTEX=1
export BQ_DATASET=polaris_core BQ_ALLOW_CORE_WRITE=1     # 只有 R1/R4 帳號可解鎖
uv run python scripts/vision_ingest_pilot.py --ticker 2330 --ticker 2891 --ingest
```

chunk id 確定性（`{ticker}-{period}-p{page:03d}-c{seq:03d}`）→ **可重跑 upsert**。
一般開發者 / agent 帳號跑 `--ingest` 會被 client 端防呆擋下（寫自己的 `polaris_dev_<name>`）。

---

## 3. 🤖 R5 — Gate2（端到端 /ask）與自助檢索驗證

**指向 dev 庫**（已備好 chunks + `v_chunk_semantic` view）跑檢索，確認 vision 頁被命中：

```bash
export GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=gemini-api-key --project=polaris-desk-team)
export VECTOR_BACKEND=bigquery BQ_DATASET=polaris_dev_wayne
uv run python - <<'PY'
from polaris.llm.gemini import active_llm
from polaris.vectorstore import get_vector_store
llm, store = active_llm(), get_vector_store()
for q in ["台積電 2025年第一季 毛利率與營業收入", "中信金控 2025 第一季 ROE 表現"]:
    print(q)
    for h in store.search(llm.embed(q), top_k=3):
        print(f"  [{h.score:.3f}] {h.id} {h.content[:60]}")
PY
```

**預期**：台積電題 top-1 = `2330-2025Q1-p004-c001`（損益表）；中信金題 top-1 = `2891-2025Q1-p006-c001`（ROE）。

**Gate2（Ragas）**：把 eval 的 `VECTOR_BACKEND/BQ_DATASET` 指到含 vision chunk 的庫（dev 或過關後的 core），
對圖表題集跑既有 Ragas，看 `/ask` 是否**引用正確數字**。
> 注意：自建 dev 庫要先有 `v_chunk_semantic` view（search 會 LEFT JOIN 它）。本 pilot 的 `polaris_dev_wayne`
> 已建好最小版 view；`polaris_core` 本來就有完整版。

---

## 4. 🤖 R7（前端）— 怎麼看出 vision chunk 在動

vision chunk 進 `chunks` 後，**檢索端零改動**，跟一般文字 chunk 走完全相同的 `/ask` → 文字 3 路 → 生成。
前端**不需任何改動**就能涵蓋圖表題。差別只在：命中的若是 vision 頁，citation 會帶**頁面參照**可回看原圖。

**怎麼確認**（指向含 vision chunk 的庫起 API，問圖表題）：

```bash
export GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=gemini-api-key --project=polaris-desk-team)
export VECTOR_BACKEND=bigquery BQ_DATASET=polaris_dev_wayne
uv run uvicorn polaris.api.main:app --port 8000 &     # 既有 API
curl -s localhost:8000/ask -X POST -H 'content-type: application/json' \
  -d '{"question":"台積電 2025 年第一季毛利率是多少？"}' | jq '.answer, .citations'
```

**預期**：答案引用 58.8%（或當頁實際數字），`citations` 帶 `2330-2025Q1-p004…`、`ticker=2330`、`period=2025Q1`、
頁碼來源。一個 vision chunk 的 `chunk_text` 長相 = `頁摘要 + key_values 條列 + 表格 markdown`（看 §0 的查詢結果）。

> 🔴 **NFR-031**：回答只陳述頁面數字、**不得給買賣建議**。每個數字都要有來源（頁碼接地）。

---

## 疑難排解

| 症狀 | 原因 / 解法 |
|---|---|
| ingestion 印「embedding 已停用」 | 沒設 `GEMINI_API_KEY`（見前置；Vertex/ADC 不能替代 embedding）。 |
| 抽取卡很久 / 429 RESOURCE_EXHAUSTED | `gemini-3-preview` Vertex QPM 限流。已內建退避 + `--throttle`；調大 `--throttle` 或分批跑。 |
| search 報 `v_chunk_semantic not found` | 自建 dev 庫缺該 view；用 §3 註解的最小版 view 建一個。 |
| `--ingest` 被擋（PermissionError core） | 正常防呆：一般帳號不可寫 `polaris_core`，設 `BQ_DATASET=polaris_dev_<你的名>`。 |
| 某頁 `extracted=FAIL` | 該頁抽取用盡重試失敗 → 誠實空白未入庫（非幻覺）；重跑該 PDF 即可補。 |
