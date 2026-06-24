# Vision-OCR 中文法說簡報入庫 — 分工與接手指南

> 目標：把 Google Drive 策展庫的**中文**法說簡報（`*M0NN_..._concall_presentation.pdf`）
> 經 vision-OCR 抽取 → 768 embedding → 寫進 **dev dataset**（`polaris_dev_wayne`，**非** polaris_core）。
> 來源資料夾：<https://drive.google.com/drive/folders/1aFEfM32eNNbpJIQ6bjFwDKZcwACz_OcJ>
> 完整中文簡報清單見 [`vision-OCR_gdrive_中文簡報清單.csv`](./vision-OCR_gdrive_中文簡報清單.csv)（111 份）。

最後更新：2026-06-25 01:0x（CST）

## 為什麼要分工

1. **本機反覆休眠**：長批次跑到一半，筆電闔蓋/閒置休眠就把背景程序收掉（`caffeinate` 擋不了闔蓋休眠）。
   → 多台機器分頭跑，每台時間短、不怕被休眠打斷。
2. **AI Studio 免費層 embedding 配額**：`embed_content_free_tier_requests` = **1000 requests/天**（PT 午夜重置）。
   逐塊 embed（pilot `--ingest` 的預設路徑）會在密集 ticker（如 2882=1455 塊）一天內爆掉。
   → **務必用批次補救腳本** `scripts/vision_reembed_recovery.py`（一個請求帶 48 塊 → 全部 ~7000 塊只要 ~145 requests）。
   → 每位接手者用**自己 Google 專案的新金鑰**（各有獨立 1000/天），分頭跑就不互相排擠。

## 目前狀態（2026-06-25）

| ticker | 公司 | GDrive中文季數 | 已抽取(JSONL) | 已入庫(BQ) | 狀態 | 負責 |
|---|---|---|---|---|---|---|
| 2303 | UMC 聯電 | 5 | 80 | 80 | ✅ DONE | — |
| 2308 | Delta 台達電 | 5 | 103 | 103 | ✅ DONE | — |
| 2317 | 鴻海 | 5 | 178 | 174 | ✅ DONE | — |
| 2357 | ASUS 華碩 | 5 | 121 | 117 | ✅ DONE | — |
| 2382 | Quanta 廣達 | 5 | 35 | 35 | ✅ DONE | — |
| 2454 | MediaTek 聯發科 | 5 | 118 | 49 | 🟡 抽取完，待 embedding | **Wayne**（JSONL 在本機）|
| 2881 | 富邦金 | 5 | 438 | 0 | 🟡 抽取完，待 embedding | **Wayne** |
| 2882 | 國泰金 | 5 | 1455 | 0 | 🟡 抽取完，待 embedding | **Wayne** |
| 2884 | 玉山金 | 5 | 266 | 0 | 🟡 抽取完，待 embedding | **Wayne** |
| 2886 | 兆豐金 | 5 | (部分) | 0 | 🔴 抽取中斷，需重跑 | 🙋 **可認領** |
| 2892 | 第一金 | 5 | 0 | 0 | 🔴 未抽取 | 🙋 **可認領** |
| 3034 | Novatek 聯詠 | 5 | 0 | 0 | 🔴 未抽取 | 🙋 **可認領** |
| 3037 | Unimicron 欣興 | 5 | 0 | 0 | 🔴 未抽取 | 🙋 **可認領** |
| 3231 | Wistron 緯創 | 5 | 0 | 0 | 🔴 未抽取 | 🙋 **可認領** |
| 3711 | ASEH 日月光 | 5 | 0 | 0 | 🔴 未抽取 | 🙋 **可認領** |
| 6505 | 台塑化 | 14 | 0 | 0 | 🔴 未抽取（量大）| 🙋 **可認領** |
| 6669 | Wiwynn 緯穎 | 2 | 0 | 0 | 🔴 未抽取 | 🙋 **可認領** |
| 1216 | 統一 | (補 2025Q1) | 0 | 0 | 🔴 只缺 2025Q1 這份 | 🙋 **可認領（小）** |

**可認領 = 從 GDrive 抓中文簡報 → 抽取 → embedding，整條自包含、不需別人的 JSONL。**
認領方式：在 GitHub issue #24 留言「我接 2892, 3034」即可（避免兩人撞同一 ticker）。

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
