# ColPali 第 4 路 round-trip 驗收 — 測試案例（給 R4 / R1 AI agent）

> **目的**：產出 PM 可驗的 gate ③ 證據。issue #17 目前只到「驗證**準備**完成」，缺實際命中率
> 數字與可重現的 result 檔。本文定義「跑什麼、產出什麼」，跑完即可關 gate ③。
> **通過條件**：`hit@5 ≥ 0.70`（TD-01 門檻）＋ 下方 sanity 控制無紅旗。

---

## 0. 角色分工
- **R1**：整備 gold（每張圖表頁配一句具辨識度的 query）。schema 見 §2，範本
  `data/gold/colpali_gold.example.json`。產出 `data/gold/colpali_gold.json`（≥20 筆、≥5 公司）。
- **R4**：在 GPU 環境跑 runner（§4），commit gold + result JSON，貼 metrics 到 #17。

## 1. 前置（R4，GPU box）
```bash
export HF_TOKEN=...                       # colpali-v1.2 依賴 gated google/paligemma-3b-mix-448
uv pip install -e '.[colpali]'
gcloud auth application-default login     # 讀 polaris_core.colpali_pages
```
池化必須一致：本 repo encoder 對 query token 做 **mean-pool**（`colpali_query_encoder.py`）。
R4 已於 #17 確認 page 端 ingest 也是 mean-pool over patches ✅。若日後改模型/池化，須重跑本驗收。

## 2. Gold schema（R1）
```json
{ "model": "vidore/colpali-v1.2", "pooling": "mean",
  "items": [ {"query": "台積電 2025Q2 各製程節點營收占比", "page_id": "<colpali_pages 真值>", "ticker": "2330", "note": "p5 長條圖"} ] }
```
規則：①一題對**一張**可辨識圖表頁（毛利率趨勢/營收分區/產能利用率…），**避免一題多頁歧義**；
②query 用自然語、貼近使用者問法；③page_id 必須是 `polaris_core.colpali_pages` 內真值
（取法見範本，或 `SELECT page_id,ticker,fiscal_period,page_num FROM colpali_pages WHERE ...`）。

## 3. 測試案例

| TC | 目的 | 步驟 | 期望 / 門檻 |
|----|------|------|------------|
| **TC-1** | 同空間維度合法性 | 編碼任一 query → 向量 | 長度 = **128**、皆 float、無 NaN/Inf |
| **TC-2** | obvious-query 自檢（fail-fast 抓 wrong-space） | 取 3–5 頁，query = 該頁**標題大字原文** | hit@1 ≥ 4/5；**若 obvious 都打不中 → encoder 不同空間，停，別跑全量** |
| **TC-3** | 全 gold round-trip（**gate ③**） | 全 gold 查 top-10 | **hit@5 ≥ 0.70**；另報 hit@1 / hit@10 / MRR |
| **TC-4** | 負控制（防退化編碼器） | 3 句無關 query（天氣/食譜…）查 top-1 | gold top1 相似度中位數 **明顯高於**負控制（separation > 0；越大越好） |
| **TC-5** | 決定性（eval 可重現） | 同 query 編碼兩次 | 逐維最大差 < 1e-5 |
| **TC-6** | 公司過濾完整性 | 帶 `filters={"company": ticker}` 查 | 回傳頁 ticker 全等於該值 |

> runner 已內建 TC-1/3/4/5/6，並把全部寫進 result JSON。**TC-2 請 R1 在 gold 前幾筆用「標題原文」當
> query 來覆蓋**（runner 不分 TC-2/TC-3，靠 gold 設計）。

## 4. 執行（R4，唯一 canonical runner）

> **沒有本機 GPU？用 Colab（免費 T4，免裝環境）** →
> [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/holajennytw/polaris-desk/blob/main/notebooks/colpali_roundtrip_colab.ipynb)
> （`notebooks/colpali_roundtrip_colab.ipynb`）：依序跑 cell——開 T4、HF 登入、GCP 登入、上傳 gold、
> 跑驗收、下載 `roundtrip_result.json`。前置：HF 先到 paligemma 頁面按同意 + 帳號有 polaris_core 讀取權。

本機（有 GPU）：
```bash
COLPALI_QUERY_ENCODER=1 uv run python scripts/colpali_roundtrip_check.py \
    --gold data/gold/colpali_gold.json --out logs/roundtrip_result.json --verbose
```
> 請用 repo 內 `scripts/colpali_roundtrip_check.py`（非本地 ad-hoc 腳本），確保 result 格式一致可比。

## 5. 我要拿到的東西（輸出契約）
runner 寫出 `logs/roundtrip_result.json`：
```json
{ "model": "...", "pooling": "mean", "dim": 128, "distance": "cosine", "top_k": 10,
  "gold_count": 20,
  "metrics": {"hit_at_1": 0.x, "hit_at_5": 0.x, "hit_at_10": 0.x, "mrr": 0.x},
  "controls": {"tc1_dim_ok": true, "tc5_determinism_max_delta": 0.0,
               "tc4_gold_vs_neg_median_separation": 0.x, "tc6_company_filter_ok": true},
  "per_query": [{"query":"...","expected":"<page_id>","got":["..."],"rank":3,"hit_at_5":true,"top1_sim":0.x}],
  "negative_control": [...], "gate": 0.7, "verdict": "PASS|FAIL" }
```
**回報（R4）**：①`git add data/gold/colpali_gold.json logs/roundtrip_result.json` → push 一條 branch；
②把 runner 印出的 metrics 表貼到 issue #17。有了這個 JSON，PM 才能客觀驗 gate ③。

## 6. 失敗分流
- **PASS（hit@5 ≥ 70%）** → 進 serving 決策：Cloud Run API 是 CPU slim image、無 GPU/torch，
  **不能**直接設 `COLPALI_QUERY_ENCODER=1`（會讓 /ask 載模型崩潰）。需把 encoder 拆成
  **GPU 推論端點**（Cloud Run GPU / Vertex endpoint / R4 GCE）再讓 API 呼叫。此為另一張 ticket。
- **FAIL（<70%）** 診斷順序：①TC-2 obvious 也低 → 不同空間（確認 model/revision/池化兩端一致）；
  ②TC-2 高但 TC-3 低 → gold 歧義或頁面非圖表，請 R1 重挑可辨識圖表頁；③負控制 separation≈0 →
  編碼退化。連兩輪修不起來 → 依 TD-01 砍場景 3 + ColPali。
