# Vision-OCR 中文法說簡報入庫 — 分工與接手指南

> 目標：把 Google Drive 策展庫的**中文**法說簡報（`*M0NN_..._concall_presentation.pdf`）
> 經 vision-OCR 抽取 → 768 embedding → 寫進 **dev dataset**（`polaris_dev_wayne`，**非** polaris_core）。
> 來源資料夾：<https://drive.google.com/drive/folders/1aFEfM32eNNbpJIQ6bjFwDKZcwACz_OcJ>
> 完整中文簡報清單見 [`vision-OCR_gdrive_中文簡報清單.csv`](./vision-OCR_gdrive_中文簡報清單.csv)（97 份）。

最後更新：2026-06-25 01:0x（CST）

## 為什麼要分工

1. **本機反覆休眠**：長批次跑到一半，筆電闔蓋/閒置休眠就把背景程序收掉（`caffeinate` 擋不了闔蓋休眠）。
   → 多台機器分頭跑，每台時間短、不怕被休眠打斷。
2. **AI Studio 免費層 embedding 配額**：`embed_content_free_tier_requests` = **1000 requests/天/專案**（PT 午夜重置）。
   ⚠️ `gemini-embedding-2` **不支援批次**（`contents=[多段]` 只回 1 個向量、其餘被丟棄）→ **1 request = 1 chunk**；
   密集 ticker（如 2882=1455 塊）就要 ~1455 requests，單一專案一天的額度大致只夠一檔。
   → 用補救腳本 `scripts/vision_reembed_recovery.py`（逐塊 embed、只補 BQ 缺的、配額耗盡優雅停可續跑）。
   → 每位接手者用**自己 Google 專案的新金鑰**（各有獨立 1000/天）；N 塊就需要 ⌈N/1000⌉ 個不同專案。

## 目前狀態（2026-06-25 11:42 CST）— ✅ 全部入庫完成（無待認領項目）

**全 20 檔中文法說簡報已抽取 + embedding 入 `polaris_dev_wayne.chunks`（清理後 **3622 塊** / 768 維）；
`polaris_core` 未動（憲法 III）。** 已做品質清理（見下「品質清理」）：移除 1191 塊純線條雜訊塊。
（6505 台塑化 已於 2026-06-25 從 GDrive 來源移除，連同入庫資料一併刪除。）

| ticker | 公司 | 入庫(BQ) | ticker | 公司 | 入庫(BQ) |
|---|---|---|---|---|---|
| 1216 | 統一 | 98 | 2882 | 國泰金 | 398 |
| 2303 | UMC 聯電 | 80 | 2884 | 玉山金 | 266 |
| 2308 | Delta 台達電 | 103 | 2886 | 兆豐金 | 213 |
| 2317 | 鴻海 | 178 | 2891 | 中信金 | 587 |
| 2330 | 台積電 | 110 | 2892 | 第一金 | 309 |
| 2357 | ASUS 華碩 | 121 | 3034 | Novatek 聯詠 | 69 |
| 2382 | Quanta 廣達 | 35 | 3037 | Unimicron 欣興 | 87 |
| 2412 | 中華電 | 137 | 3231 | Wistron 緯創 | 140 |
| 2454 | MediaTek 聯發科 | 118 | 3711 | ASEH 日月光 | 120 |
| 2881 | 富邦金 | 438 | 6669 | Wiwynn 緯穎 | 15 |

> 下一步（非本檔範圍）：R1 Gate1 抽查（`*_gate1.csv`）→ 達標後由 R4 帳號把 dev 塊
> 合併進 `polaris_core`（一般開發者 / agent 不可寫 core）。

### 🧹 品質清理（2026-06-25，jenny/main 8a39097）
入庫後審查發現 vision `table_markdown` 的長分隔列（`-----`）被切塊器硬切成**純線條塊**（0 資訊）：
原 5007 塊中有 **1191 塊（24%）** 是這種雜訊（2882 國泰金占其塊數 73%），且造成 85% 的重複文字。
- **源頭修掉**：`sanitize.is_low_information()`（整塊只剩繪製字元 → <2 實字）同時接進
  `validate_for_ingestion`（reject）與 `chunker.chunk_page`（切塊時略過）→ 雙層防線，重跑不會再生。
  真表格 / 含數字列 / 「目錄」這類短標題都保留。
- **清掉舊資料**：dev BQ 刪 1191 塊（其後再移除 6505 台塑化 194 塊）→ 3622；重複冗餘 1392→204（剩的是各季合理重複的免責聲明，保留）。
- **驗證**：embedding 全 768 維非退化；最近鄰一致性測試（國泰金 IFRS 17 → 命中其他 IFRS 17 / 清償能力塊）OK。
- R1 Gate1 抽查時若仍見純線條塊請回報（理論上已不會有）。

### ⚠️ embedding 配額重點（踩過的雷，務必照做）
- `gemini-embedding-2` **不支援批次**：`contents=[多段]` 只回 1 個向量、其餘被丟棄 →
  **1 request = 1 chunk**，免費層 **1000 requests/天/GCP 專案**（非每分鐘）。
- 補救腳本 `vision_reembed_recovery.py` 已修正成逐塊 embed；多把 key 逗號分隔放 `.env`，
  **不同專案**的 key 才各有獨立 1000/天（同專案多把共用一份額度）。N 塊就需要 ⌈N/1000⌉ 個專案。
- 抽取（Vertex）不吃 embedding 額度；可與 embedding 並行。

## 接手步驟（每個 ticker 自包含）

### 0. 環境（一次性）
```bash
cd polaris-desk
uv venv --python 3.13 && uv pip install -e ".[dev,vision]"   # vision = pymupdf
```

### 1. 取得你自己的 embedding 金鑰（重點）
到 <https://aistudio.google.com/apikey> 用**自己的 Google 帳號 / 一個新專案**建一把 API key
（各專案獨立 1000 requests/天）。**不要**用 Wayne 那把（已用罄）。

### 2. 從 GDrive 抓你認領 ticker 的「中文」簡報
進來源資料夾 → `<ticker>_<名>/` → 只抓檔名含 `M0NN`（中文；`E0NN` 是英文，不要）、
結尾 `_concall_presentation.pdf` 的檔。放到 repo 的 `data/<ticker>_x/` 底下：
```bash
mkdir -p data/2892_x        # 例：認領 2892
# 把下載的 2892_*M*_concall_presentation.pdf 放進 data/2892_x/
```
（哪些季別/檔名見 [`vision-OCR_gdrive_中文簡報清單.csv`](./vision-OCR_gdrive_中文簡報清單.csv)。）

### 3. 抽取（vision-OCR → JSONL，**不**入庫；不吃 embedding 配額）
```bash
export GEMINI_USE_VERTEX=1 VISION_EXTRACTION=1
export GEMINI_MODEL_FLASH=gemini-2.5-flash GEMINI_MODEL_PRO=gemini-2.5-pro   # GA 模型，避開 preview QPM
uv run python scripts/vision_ingest_pilot.py --ticker 2892 --concurrency 4 --throttle 0.5
# 產出 data/vision_chunks/2892.jsonl + 2892_gate1.csv（人工抽查用）
```
> 用 GA `gemini-2.5-flash`（非預設 preview）才不會被 Vertex QPM 卡住。
> 抽取走 **Vertex**（ADC：先 `gcloud auth application-default login`），不需 embedding 金鑰。

### 4. 批次 embedding 入庫（用你的新金鑰；批次 → 不爆 1000/天）
```bash
export GEMINI_API_KEY='你自己的新金鑰'
export BQ_DATASET=polaris_dev_wayne VECTOR_BACKEND=bigquery     # 共用組裝庫；無寫入權限就先用自己的 polaris_dev_<name>，再請 Wayne 合併
uv run python scripts/vision_reembed_recovery.py --ticker 2892
# 只 embed「BQ 還沒有」的 chunk_id（idempotent、可重跑）；批次 48/req、~960 contents/分
```
撞 429 會**優雅停**並印出已補/未補數，配額恢復後重跑同指令即續。

### 5. 驗收
```bash
bq query --use_legacy_sql=false \
 'SELECT fiscal_period, COUNT(*) FROM `polaris-desk-team.polaris_dev_wayne.chunks`
  WHERE ticker="2892" GROUP BY 1 ORDER BY 1'
```
塊數應與 `data/vision_chunks/2892.jsonl` 行數相符（誤差幾塊＝極短頁被 validate 擋掉，正常）。

## 硬規矩
- 🔴 **只寫 dev dataset**（`polaris_dev_*`），**不可寫 `polaris_core`**（憲法 III；腳本已防呆會拒絕）。
- embedding 一律 `gemini-embedding-2` / 768 維（與 polaris_core 同向量空間）；**別**改成 Vertex/別的 embedding 模型。
- 金鑰只放環境變數 / `.env`（已 gitignore），**永不 commit**。
- 抽取用 GA flash；遇 429 腳本已有 retry / 優雅停，不要拿掉。

## 檔名小坑（已修）
策展庫有兩種命名：`2330_20260417M001_...`（無底線）與 `2317_20250514_M002_...`（日期後多一底線）。
`vision_ingest_pilot.py` / `vision_reembed_recovery.py` 的解析已支援兩種（`[ME]` 前可選底線）。
