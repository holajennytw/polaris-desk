# Polaris Desk 協作開發環境 SOP v1.1

**目的**：讓 7 位成員在「同一份可信資料」上協同開發，且把成本壓在 GCP 免費額度內。
**適用範圍**：4 週 MVP 開發期（W1 ~ W4）。
**文件擁有者**：角色 1（PM）。**基礎設施擁有者**：角色 4（資料工程師）。

> **基礎設施現況（2026-06-02）**：GCP 專案 **`polaris-desk-team`**（Project ID = `polaris-desk-team`）已由 PM 建立並連結計費帳戶。Phase 1（§3）以後由角色 4 執行，**從 §3.1 開始**。
> **本團隊用個人 `@gmail.com` 帳號、無 Google Workspace 網域**，故權限以個別 `user:` 綁定（見 §3.4），不使用 Google Group。

---

## 0. 核心原則（先讀這段）

1. **算一次、大家讀**：所有人共用一份唯讀的 canonical 資料，個人實驗寫進自己的 scratch，不互相覆蓋。
2. **共用不等於同寫**：禁止 7 個人各自全量重建 index 或重跑 ingestion，那會放大成本並造成資料不一致。
3. **預設讀 `polaris_core`、寫 `polaris_dev_<name>`**：程式碼層級就要鎖死這個預設。
4. **成本守則**：dev 期所有用量壓在 BigQuery 與 Cloud Run 免費額度內，$300 credit 留到 W4 demo。

---

## 1. 角色與權責

| 角色 | 權責 | 對 `polaris_core` 權限 |
| --- | --- | --- |
| 角色 1（PM） | 維護本 SOP、建立專案、設定預算告警、核准 schema 變更 PR | READER |
| 角色 4（資料工程師） | 建置基礎設施、唯一可寫入 canonical 的人、跑 ingestion | OWNER／WRITER |
| 角色 2（AI 架構師） | 審查 schema migration、retrieval 設定 | READER |
| 其餘開發者 | 讀 core、在自己的 scratch 做實驗 | READER |

> 只有角色 4 能寫入 `polaris_core`。其他人一律唯讀。

---

## 2. 環境總覽（三層）

單一團隊 GCP Project：`polaris-desk-team`

```
polaris-desk-team
├─ Cloud Storage：gs://polaris-desk-raw       ← PDF 原始檔（檔案層單一真實來源）
├─ BigQuery dataset：polaris_core             ← canonical，全員唯讀
│    chunks / embeddings（VECTOR INDEX）/ colpali_index / financial_metrics / ontology
└─ BigQuery dataset：polaris_dev_<name>       ← 每人一個，可寫，做實驗用
```

設定一致的占位符（請全團統一）：

| 變數 | 值 |
| --- | --- |
| `PROJECT_ID` | `polaris-desk-team` |
| `REGION` | `asia-east1`（台灣，低延遲與資料落地） |
| `RAW_BUCKET` | `gs://polaris-desk-raw` |
| `CORE_DATASET` | `polaris_core` |
| 團隊成員 | 7 位成員的個人 `@gmail.com`（IAM 以 `user:` 個別綁定，見 §3.4） |

> **注意**：建立 VECTOR INDEX 前，請角色 4 先確認所選 REGION 支援 BigQuery `CREATE VECTOR INDEX`。若不支援，改用支援的鄰近區域並同步更新本表。

---

## 3. Phase 1：一次性基礎設施建置（角色 4 執行，約 30 分鐘）

> **Phase 0 已完成**：專案 `polaris-desk-team` 與計費已就緒。角色 4 直接從 §3.1 開始。

以下用 `gcloud`／`bq` 指令快速建置。建議事後由角色 4 把同一份設定補成 Terraform（PRD §23.3）以便重建。

### 3.1 設定 project 與 API

```bash
gcloud config set project polaris-desk-team

gcloud services enable bigquery.googleapis.com run.googleapis.com \
  storage.googleapis.com secretmanager.googleapis.com
```

### 3.2 建立原始檔 bucket

```bash
gcloud storage buckets create gs://polaris-desk-raw \
  --location=asia-east1 \
  --uniform-bucket-level-access
```

### 3.3 建立 canonical dataset

```bash
bq --location=asia-east1 mk --dataset \
  --description "canonical read-only corpus" \
  polaris-desk-team:polaris_core
```

### 3.4 設定權限（IAM）— 個別 user 綁定

本團隊無 Workspace 網域，**逐一綁定 7 位成員的 gmail**（不使用 Google Group）。

```bash
# 把 7 位成員的 gmail 填進來
MEMBERS=(
  "member1@gmail.com"
  "member2@gmail.com"
  "member3@gmail.com"
  "member4@gmail.com"
  "member5@gmail.com"
  "member6@gmail.com"
  "member7@gmail.com"
)

# 每人都能在 project 內跑查詢（執行 job 的權限）
for m in "${MEMBERS[@]}"; do
  gcloud projects add-iam-policy-binding polaris-desk-team \
    --member="user:$m" \
    --role="roles/bigquery.jobUser"
done
```

把每位成員設為 `polaris_core` 的唯讀 READER：

```bash
# 1. 匯出現有 access 設定（此檔含真實 email/ACL，已在 .gitignore，不要 commit）
bq show --format=prettyjson polaris-desk-team:polaris_core > core_access.json

# 2. 在 core_access.json 的 "access" 陣列，每位成員加一筆：
#    { "role": "READER", "userByEmail": "member1@gmail.com" }
#    { "role": "READER", "userByEmail": "member2@gmail.com" }
#    ...（共 7 筆）

# 3. 套用
bq update --source=core_access.json polaris-desk-team:polaris_core
```

> 應用程式用的 service account 採最小權限，金鑰存進 Secret Manager，**不進版控**。
> 新增／移除成員時，記得同步更新 `bigquery.jobUser` 綁定與 `polaris_core` 的 READER 名單。

### 3.5 設定成本護欄（重要）

1. **預算告警**：

   ```bash
   gcloud billing budgets create \
     --billing-account=YOUR_BILLING_ACCOUNT_ID \
     --display-name="polaris-dev-budget" \
     --budget-amount=400USD \
     --threshold-rule=percent=0.5 \
     --threshold-rule=percent=0.9
   ```

2. **per-user 查詢配額**：到 Console 的「IAM 與管理 → 配額與系統限制」，搜尋 `Query usage per day per user`，設一個每人每日掃描上限（例如 200 GB／人／日），防止單人亂掃表把免費 1 TB／月吃光。

---

## 4. Phase 2：canonical 資料建置（角色 4 執行，一次性）

### 4.1 建立分區與分群表（控制掃描量的關鍵）

```sql
CREATE TABLE polaris_core.chunks (
  chunk_id      STRING,
  stock_id      STRING,
  doc_type      STRING,
  fiscal_period STRING,
  published_at  DATE,
  chunk_text    STRING,
  embedding     ARRAY<FLOAT64>
)
PARTITION BY published_at
CLUSTER BY stock_id, doc_type;
```

> 所有查詢都應帶 `published_at` 範圍與 `stock_id` 條件，才能命中 partition／cluster，把掃描量壓到最小。

### 4.2 建立向量索引（對齊 PRD §15）

```sql
CREATE VECTOR INDEX chunks_emb_idx
ON polaris_core.chunks(embedding)
OPTIONS(index_type = 'IVF', distance_type = 'COSINE');
```

> ⚠️ **兩個前提**：①`asia-east1` 須支援 `CREATE VECTOR INDEX`（建前先確認，否則改鄰近區域並更新 §2）。
> ②**BigQuery 不會在少於 5,000 列的表上建立向量索引**。100 份法說稿切 chunk 後若不足 5,000 列，索引不會生成，`VECTOR_SEARCH` 會自動退回暴力搜尋（demo 仍可用，但要知道）。

### 4.3 跑一次 ingestion

由角色 4 用 ingestion pipeline 把 100 份法說稿、財務指標、ColPali index、ontology 一次寫入 `polaris_core`。embedding 與 ColPali **只在此處計算一次**，其他人不得重算。對齊 PRD §1.5 的 W1 Day 5「Ontology 凍結 + 100 份法說稿入庫」。

完成後通知全團：**canonical 已就緒，可開始開發**。

---

## 5. Phase 3：每位開發者上線步驟（給大家的 onboarding）

每個人只需做一次。預計 10 分鐘完成。

### 步驟 1：登入並指定 project

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project polaris-desk-team
```

### 步驟 2：建立自己的 scratch dataset

把 `<name>` 換成你的英文名（例如 `wayne`）：

```bash
bq --location=asia-east1 mk --dataset \
  polaris-desk-team:polaris_dev_<name>
```

### 步驟 3：取得共用設定

`PROJECT_ID` 與 `CORE_DATASET` 已在版控的 config 模組中，全團一致，不要自行改動。只需在本機設定自己的 scratch：

```bash
# 寫進本機 .env（不要進版控）
echo "DEV_DATASET=polaris_dev_<name>" >> .env
```

範例 config 讀取邏輯：

```python
import os

PROJECT_ID   = "polaris-desk-team"        # 進版控，全團一致
CORE_DATASET = "polaris_core"             # 進版控，唯讀
DEV_DATASET  = os.environ["DEV_DATASET"]  # 個人覆寫，可寫
```

### 步驟 4：驗證讀取權限

```bash
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) AS n FROM `polaris-desk-team.polaris_core.chunks`'
```

> 能回傳數字即代表 onboarding 成功。

---

## 6. 日常開發守則

1. **讀 `polaris_core`，寫 `polaris_dev_<name>`**。任何寫入操作的目標 dataset 一律是自己的 scratch。
2. 禁止對 `polaris_core` 做 ingestion、重建 index、改 schema。需要新資料或新欄位，走第 7 章流程。
3. 每次查詢必帶 partition filter（`published_at` 範圍）與 `stock_id` 條件。
4. 大查詢前先 dry-run 估成本：

   ```bash
   bq query --dry_run --use_legacy_sql=false 'YOUR_SQL'
   ```

5. 重複查詢盡量用相同 SQL 以命中 cached results（快取結果免費）。

---

## 7. Schema 變更流程

1. 在自己的 scratch 驗證新 schema 或新欄位可行。
2. 開 PR，附上 migration SQL 檔（放 `migrations/` 目錄）與變更理由。
3. 角色 2（AI 架構師）審查，角色 1（PM）核准。
4. 由角色 4 對 `polaris_core` 套用 migration，並重建受影響的 index。
5. 通知全團 canonical schema 已更新版本。

> 禁止繞過此流程直接動 canonical，避免 schema drift。

---

## 8. 成本護欄速查

| 機制 | 設定者 | 效果 |
| --- | --- | --- |
| canonical 算一次 | 角色 4 | 避免 embedding／ColPali 被乘以人數 |
| partition + cluster | 角色 4 | 把每次查詢掃描量壓進免費 1 TB／月 |
| 預算告警 50%／90% | 角色 1 | 超支前先收到通知 |
| per-user 查詢配額 | 角色 4 | 防單人亂掃表 |
| Cloud Run scale to zero | 全員 | 沒人用就不計費 |
| $300 credit 留到 W4 | 角色 1 | dev 期走免費額度，demo 期才動用 |

> 不要為了協作引入外部託管向量庫（如 Qdrant Cloud）。它的免費 tier 容量不足以承載 ColPali leg，會被迫升級為月費叢集，與省錢目標衝突。

---

## 9. 失敗排查（Fail Fast：Status / Root Cause / Suggested Fix）

| 現象 | 最可能原因 | 第一步排查 |
| --- | --- | --- |
| 查 core 報 permission denied | 你的 gmail 沒被綁定，或缺 jobUser | 確認帳號已加入 §3.4 的 `user:` 名單（READER + jobUser） |
| 查詢費用異常高 | 沒帶 partition filter，全表掃描 | 加 `published_at` 範圍與 `stock_id` 條件，先 dry-run |
| 寫入失敗 | 誤把目標設成 `polaris_core` | 確認寫入目標是 `polaris_dev_<name>` |
| 大家資料對不上 | 有人在 scratch 改了卻當成 canonical | 一律以 `polaris_core` 為準，scratch 只是個人實驗 |
| VECTOR INDEX 建立失敗 | REGION 不支援，或表 < 5,000 列 | 改用支援的鄰近區域（更新 §2）；列數不足則等資料補足或接受暴力搜尋 |
| `project not found` / 設不了 project | 用到了顯示名稱而非 Project ID | 一律用 Project ID `polaris-desk-team` |

---

## 10. 啟動檢查清單（Definition of Ready）

- [x] 單一團隊 project `polaris-desk-team` 已建立並開啟計費
- [ ] 預算告警與 per-user 配額已設定
- [ ] `gs://polaris-desk-raw` 已建立
- [ ] `polaris_core` 已建立，7 位成員（`user:`）為 READER + `bigquery.jobUser`
- [ ] canonical（chunks / embeddings / VECTOR INDEX / 財務指標 / ontology）已 ingest 一次
- [ ] 7 位成員各自建立 scratch dataset 並通過讀取驗證
- [ ] config 模組（`PROJECT_ID` / `CORE_DATASET`）已進版控

> 全部勾選後，協作開發環境即就緒。目前只完成第 1 項，其餘為角色 4 的 Phase 1／2 工作。

---

_版本：v1.1　|　對應 PRD：§13.4（向量檢索）、§23（部署）、§24（成本）_
_v1.1 變更：專案改用乾淨 Project ID `polaris-desk-team`；IAM 從 Google Group 改為個別 `user:` 綁定（團隊用個人 gmail、無 Workspace 網域）；補上 Phase 0 現況、向量索引 region／5,000 列前提，與 Project ID vs 顯示名稱排查。_
