# 真人操作 checklist — 啟用 Google OAuth + Firestore（R7-1）

> **給誰**：R2 / PM（有 GCP 專案權限的人）+ R7（Vercel 那段）。
> **前提**：後端程式碼已就緒（`auth.py` / `user_store.py` / `/history` / `/subscriptions`，PR #101/#103）。
> 這份只列**程式做不了、需真人在 console / CLI 操作**的步驟。做完即可全鏈跑登入版。
> **專案值**：`PROJECT=polaris-desk-team`、`REGION=asia-east1`、Cloud Run 服務 `polaris-api`、
> runtime SA `polaris-run@polaris-desk-team.iam.gserviceaccount.com`、
> 後端 URL `https://polaris-api-14326813937.asia-east1.run.app`。

先設好變數（其餘指令會用到）：
```bash
export PROJECT=polaris-desk-team
export REGION=asia-east1
export SA=polaris-run@polaris-desk-team.iam.gserviceaccount.com
export VERCEL_DOMAIN=https://<R7-的-vercel-網域>      # ← 填 R7 實際網域
gcloud config set project "$PROJECT"
```

---

## ① OAuth consent screen + OAuth Client（Console only）

> gcloud 無法建 OAuth Client ID，必走 Console。

1. **OAuth 同意畫面**：Console → 「API 和服務 → OAuth 同意畫面」
   - User Type：**Internal**（同 Google Workspace 組織內）或 **External**（要加測試使用者 email）。
   - 填 App name、support email、developer email → 儲存。
2. **建 OAuth Client**：Console → 「API 和服務 → 憑證 → 建立憑證 → OAuth 用戶端 ID」
   - 應用程式類型：**Web application**
   - **Authorized JavaScript origins**：`https://<R7-的-vercel-網域>`
   - **Authorized redirect URIs**：`https://<R7-的-vercel-網域>/api/auth/callback/google`
     （本機開發另加 `http://localhost:3000/api/auth/callback/google`）
   - 建立後記下 **Client ID** 與 **Client Secret**。

> 產出：`GOOGLE_CLIENT_ID`（給後端 + 前端）、`GOOGLE_CLIENT_SECRET`（**只給前端**）。

---

## ② 啟用 Firestore + 給 runtime SA 寫入權限（gcloud）

```bash
# 啟用 API
gcloud services enable firestore.googleapis.com

# 建 Firestore 資料庫（Native 模式，asia-east1；一個專案只能建一次）
gcloud firestore databases create --location="$REGION" --type=firestore-native

# runtime SA 加 Datastore User（Firestore 讀寫；最小權限，與既有 BQ/Secret 角色同風格）
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA" \
  --role="roles/datastore.user"
```

> 後端用 ADC（runtime SA）連 Firestore → **不需金鑰檔**。本機開發若要連真 Firestore：
> `gcloud auth application-default login`。

---

## ③ Cloud Run 設環境變數 + 重新部署（gcloud）

後端只需 **`GOOGLE_CLIENT_ID`**（驗 id_token 的 aud；非機密）+ CORS 放行 Vercel 網域：

```bash
gcloud run services update polaris-api --region="$REGION" \
  --update-env-vars "GOOGLE_CLIENT_ID=<上面拿到的 client id>,POLARIS_CORS_ORIGINS=$VERCEL_DOMAIN"
```

> - 後端**不需**也**不該**拿 client secret。
> - 若 `polaris_core` 與 Firestore 在同專案，runtime SA 已有 BQ 角色，這步只補 env。
> - 部署新 image（含 `google-cloud-firestore` 依賴）：照 [`上雲_Cloud_Run_runbook.md`](./上雲_Cloud_Run_runbook.md) 既有流程 `gcloud run deploy`。

---

## ④ Vercel 前端環境變數（Vercel dashboard / CLI）

前端（NextAuth）需要：

| 變數 | 值 | 機密 |
|---|---|---|
| `GOOGLE_CLIENT_ID` | ①的 Client ID | 否 |
| `GOOGLE_CLIENT_SECRET` | ①的 Client Secret | ✅ 機密 |
| `NEXTAUTH_SECRET` | `openssl rand -base64 32` 產 | ✅ 機密 |
| `NEXTAUTH_URL` | `https://<R7-的-vercel-網域>` | 否 |
| `NEXT_PUBLIC_API_BASE` | `https://polaris-api-14326813937.asia-east1.run.app` | 否 |

```bash
# 例（Vercel CLI）；機密項用 Vercel 加密儲存，勿寫進 repo（憲法 III）
vercel env add GOOGLE_CLIENT_SECRET production
vercel env add NEXTAUTH_SECRET production
# ...其餘同理
```

---

## ⑤ 驗收（做完逐項打勾）

- [ ] 前端點 Google 登入 → 跳 Google 同意 → 導回，AppShell 顯示真實使用者名/頭像
- [ ] 開瀏覽器 DevTools：呼叫 `/research` 的請求帶 `Authorization: Bearer …`
- [ ] 跑一次研究 → `POST /history` 201/200；重整 `/history` 頁看得到該筆
- [ ] 點開歷史某筆 → **完整還原**當時答案（不重打 `/research`）
- [ ] `/subscriptions` 勾選公司 → 儲存 → 重整仍在
- [ ] 用**另一個** Google 帳號登入 → 看不到前一位的紀錄（隔離）
- [ ] **匿名降級**：登出 / 不帶 token → `/history` 回 401、前端退 localStorage、`/ask` 仍可用（斷網備援不破）
- [ ] 機密（client secret / NEXTAUTH_SECRET）只在 Vercel env，未進 repo

### 快速 curl 煙測（替換 `<ID_TOKEN>` 為前端 DevTools 複製的 token）
```bash
API=https://polaris-api-14326813937.asia-east1.run.app
# 匿名 → 401
curl -s -o /dev/null -w "anon /history -> %{http_code}\n" "$API/history"
# 登入 → 200
curl -s -H "Authorization: Bearer <ID_TOKEN>" "$API/history" | head -c 200
```

---

## 注意
- 這些都是 **Demo / 測試可用**的設定（非「Demo 後」）；登入版要在測試期就跑得動。
- 唯一真正機密：`GOOGLE_CLIENT_SECRET`、`NEXTAUTH_SECRET` → Vercel env（加密）/ Secret Manager，永不 commit。
- 後端零金鑰檔：Firestore + BQ 都走 runtime SA 的 ADC。
