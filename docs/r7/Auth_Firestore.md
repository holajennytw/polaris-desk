# Google OAuth + Firestore — 串接指南與操作 Checklist

> 維護：R7
> 合併自：`frontend/串接指南_Auth_Firestore.md`、`frontend/測試_Auth_Firestore_checklist.md`
> 對應決策：議題 A/B/C/E（詳見 `docs/r7/協作會議紀錄_20260618.md`）

---

## 現況（2026-06-20 更新）

**後端已完成並驗證（R2）**：
- ✅ ① OAuth client（Console）：Web client 已建，JS origin + redirect 含 localhost 與 `polaris-web`
- ✅ ② Firestore：`(default)` DB @ asia-east1 + SA `polaris-run` `roles/datastore.user`
- ✅ ③ polaris-api env：`GOOGLE_CLIENT_ID` + `POLARIS_CORS_ORIGINS` 已設（rev `polaris-api-00011`）
- ✅ Firestore round-trip de-risk：真 `UserStore` 對 `(default)` DB 寫讀全 PASS

**剩餘事項（critical path）**：

| # | 待辦 | Owner |
|---|------|-------|
| 1 | 確認 7 個帳號都在 Test users（尤其 `Arronyang0416@gmail.com`） | PM/Wayne |
| 2 | `GOOGLE_CLIENT_SECRET` + `NEXTAUTH_SECRET` 進 Secret Manager | PM/Wayne |
| 3 | 部署 `polaris-web` 到 Cloud Run | R7 |
| 4 | 端到端驗收 ⑤ | R7 執行 / Wayne 簽核 |

---

## 架構全貌

```
[使用者]
   │ 1. 點 Google 登入
   ▼
[Cloud Run polaris-web / NextAuth]  ──2. 拿到 Google id_token──┐
   │                                                           │
   │ 3. 呼叫後端時帶 Authorization: Bearer <id_token>           │
   ▼                                                           │
[Cloud Run polaris-api]                                        │
   │ 4. 驗 id_token（Google JWKS, aud=client_id）→ 取 sub        │
   │ 5. 讀寫 Firestore（按 sub 隔離）                            │
   ▼                                                           │
[Firestore]  users/{sub}/sessions/*  +  users/{sub}（訂閱）   ◀┘
```

**專案值**：`PROJECT=polaris-desk-team`、`REGION=asia-east1`
runtime SA：`polaris-run@polaris-desk-team.iam.gserviceaccount.com`
後端 URL：`https://polaris-api-14326813937.asia-east1.run.app`
前端 URL：`https://polaris-web-14326813937.asia-east1.run.app`

---

## 分工

| 步驟 | 負責 | 內容 |
|---|---|---|
| 建 Google OAuth Client | **R2/PM** | GCP Console → OAuth 2.0 Client（Web） |
| NextAuth + 登入 UI | **R7** | `[...nextauth]/route.ts`、`signIn/signOut` |
| 後端 JWT 驗證 | **R2/R3** | FastAPI dependency（無 token = 匿名） |
| Firestore store + 端點 | **R2/R3** | `/history`(GET/POST/GET{id})、`/subscriptions`(GET/POST) |
| CORS + SA 權限 | **R2** | Cloud Run 加 Vercel 網域；runtime SA 加 `roles/datastore.user` |

---

## 環境變數對照

| 變數 | 放哪 | 用途 |
|---|---|---|
| `GOOGLE_CLIENT_ID` | polaris-web + polaris-api | OAuth client id；後端驗 `aud` |
| `GOOGLE_CLIENT_SECRET` | polaris-web only（Secret Manager） | NextAuth 換 code；**後端不需要** |
| `NEXTAUTH_SECRET` | polaris-web（Secret Manager） | NextAuth session 簽章 |
| `NEXTAUTH_URL` | polaris-web | `https://polaris-web-14326813937.asia-east1.run.app` |
| `NEXT_PUBLIC_API_BASE` | polaris-web | `https://polaris-api-14326813937.asia-east1.run.app` |

---

## 前端（R7）實作

### NextAuth route

```ts
// src/app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

const handler = NextAuth({
  providers: [Google({ clientId: process.env.GOOGLE_CLIENT_ID!, clientSecret: process.env.GOOGLE_CLIENT_SECRET! })],
  callbacks: {
    async jwt({ token, account }) {
      if (account?.id_token) token.idToken = account.id_token;
      return token;
    },
    async session({ session, token }) {
      (session as any).idToken = token.idToken;
      return session;
    },
  },
});
export { handler as GET, handler as POST };
```

### 登入 / 登出

```ts
import { signIn, signOut, useSession } from "next-auth/react";
<button onClick={() => signIn("google")}>使用 Google 登入</button>
<button onClick={() => signOut()}>登出</button>
```

### 呼叫後端帶 Bearer

```ts
async function authHeaders() {
  const session = await getSession();
  const t = (session as any)?.idToken;
  return t ? { Authorization: `Bearer ${t}` } : {};
}
```

### 匿名降級

不帶 token → 後端視為匿名；`/history` 回 401 → 前端 fallback localStorage。此路徑為斷網 / token-free CI 備援，不是 Demo 主路徑。

---

## 後端（R2/R3）實作

後端程式碼已就緒（`auth.py`、`user_store.py`，PR #101/#103）。

### auth.py（關鍵片段）

```python
async def current_user(authorization: str | None = Header(None)) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return _verify(authorization[7:])  # None = 匿名
```

### user_store.py（Firestore 結構）

```
users/{uid}
  ├─ tickers: ["2330", "2454"]      # 訂閱清單
  └─ sessions/{sessionId}
        origin: "research" | "peer"
        query:  string
        tickers: string[]
        created_at: timestamp
        result: { final_answer, evidence[], react_steps[], citations[] }
```

---

## 端點契約

### POST /history（需 Bearer）
```json
{ "origin": "research", "query": "台積電 2026Q1 法說重點", "tickers": ["2330"],
  "result": { "final_answer": "...", "evidence": [], "react_steps": [], "citations": [] } }
```
→ `{ "record_id": "abc123", "status": "ok" }`

### GET /history（需 Bearer）
```json
[{ "id": "abc123", "origin": "research", "query": "...", "tickers": ["2330"],
   "created_at": "2026-06-18T10:30:00Z" }]
```

### GET /history/{id}（需 Bearer）→ 含完整 `result` 欄位供還原

### GET /subscriptions → `{ "tickers": ["2330","2454"] }`
### POST /subscriptions body `{ "tickers": [...] }` → `{ "status":"ok", "tickers":[...] }`

---

## 真人操作 Checklist（ops）

### 先設變數

```bash
export PROJECT=polaris-desk-team
export REGION=asia-east1
export SA=polaris-run@polaris-desk-team.iam.gserviceaccount.com
export WEB_URL=https://polaris-web-14326813937.asia-east1.run.app
gcloud config set project "$PROJECT"
```

### ① OAuth Client（Console only）

1. Console → API 和服務 → OAuth 同意畫面 → **External**；把所有會登入的帳號加進 **Test users**
2. 建 OAuth Client ID（Web application）
   - JS origins：`http://localhost:3000`、`$WEB_URL`
   - Redirect URIs：`http://localhost:3000/api/auth/callback/google`、`$WEB_URL/api/auth/callback/google`
3. 記下 **Client ID**（前後端都要）、**Client Secret**（前端 only）

### ② Firestore + SA 權限

```bash
gcloud services enable firestore.googleapis.com
gcloud firestore databases create --location="$REGION" --type=firestore-native
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA" --role="roles/datastore.user"
```

### ③ polaris-api（後端）補 env

```bash
gcloud run services update polaris-api --region="$REGION" \
  --update-env-vars "GOOGLE_CLIENT_ID=<client id>,POLARIS_CORS_ORIGINS=http://localhost:3000,$WEB_URL"
```

### ④ polaris-web（前端）部署

```bash
# 機密進 Secret Manager
printf '%s' '<client secret>'        | gcloud secrets create google-client-secret --data-file=-
openssl rand -base64 32 | tr -d '\n' | gcloud secrets create nextauth-secret      --data-file=-
for S in google-client-secret nextauth-secret; do
  gcloud secrets add-iam-policy-binding "$S" \
    --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
done

# 部署
gcloud run deploy polaris-web --region="$REGION" --image="<polaris-web 鏡像>" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLIENT_ID=<client id>,NEXTAUTH_URL=$WEB_URL,NEXT_PUBLIC_API_BASE=https://polaris-api-14326813937.asia-east1.run.app" \
  --set-secrets "GOOGLE_CLIENT_SECRET=google-client-secret:latest,NEXTAUTH_SECRET=nextauth-secret:latest"
```

### ⑤ 驗收

- [ ] Google 登入 → AppShell 顯示真實使用者名/頭像
- [ ] DevTools：呼叫 `/research` 帶 `Authorization: Bearer …`
- [ ] 跑研究 → `POST /history` 成功；重整 `/history` 看得到
- [ ] 點歷史某筆 → 完整還原當時答案
- [ ] `/subscriptions` 勾選公司 → 儲存 → 重整仍在
- [ ] 另一個帳號登入 → 看不到前一位的紀錄（隔離）
- [ ] 匿名降級：不帶 token → `/history` 回 401、前端退 localStorage、`/ask` 仍可用

```bash
# 快速 curl 煙測
API=https://polaris-api-14326813937.asia-east1.run.app
curl -s -o /dev/null -w "anon /history -> %{http_code}\n" "$API/history"
curl -s -H "Authorization: Bearer <ID_TOKEN>" "$API/history" | head -c 200
```

---

## 注意事項

- `GOOGLE_CLIENT_SECRET`、`NEXTAUTH_SECRET` → **只進 Secret Manager**，永不 commit
- 後端零金鑰檔：Firestore + BQ 都走 runtime SA ADC
- `sub` 當主鍵，不用 email（email 可變）
- OAuth app 維持 Testing 模式即可（>100 users 或公開才需發布）
