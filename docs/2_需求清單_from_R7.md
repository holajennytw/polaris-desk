# 需求清單 — from R7（前端 / Demo 全端）

> **用途**：R7 在開發前端 / Demo 過程中，需要其他角色（主要是 R2 架構師）協助評估或提供的事項清單。
> **維護者**：R7（李靜雲）。**讀者**：R2 / R3 / R4 / R1。
> **優先級**：🔴 擋路（不做不能往下） · 🟡 排期內 · 🟢 nice-to-have（有餘力才做）。
> **狀態**：📥 待評估 · 🔄 評估中 · ✅ 結論已出 · ❌ 不做。

> **背景提醒**：R2 對 R7 的**核心依賴（thin API + 上雲後端）已全部解除**（2026-06-18，
> 見 [`R7_frontend_開工指南.md`](./R7_frontend_開工指南.md) 頂部狀態更新）。本清單為**核心依賴之外**的後續 / 加分項。

---

## 需求一覽

| # | 需求 | 對象 | 優先級 | 狀態 |
|---|---|---|---|---|
| R7-1 | 帳號登入（Google OAuth）+ 使用者活動紀錄儲存 | R2 | 🟡 排期內（建議 Demo 後） | ✅ 結論已出（架構拍板） |

> ⚠️ **文件分流提醒**：R7 在 branch `feature/my-frontend-work_2026_0617` 的
> `docs/cross-role-collab/` 下另有更完整的 `R2_需求清單_from_R7.md` 與
> `開會議程_待決策事項_2026-06-18.md`。本節是 **R2 對該需求的架構結論**，
> 待 merge 後應回填進那邊的決策追蹤表（議題 A / E + Auth）。

---

## R7-1 · 帳號登入（Google OAuth）+ 使用者活動紀錄儲存 〔🟡 排期內，建議 Demo 後〕

**提出者**：R7　**對象**：R2　**優先級**：🟡 排期內　**狀態**：✅ 結論已出（2026-06-18，R2 架構拍板）

### 需求（澄清後）
1. **登入**：前端支援帳號登入（Google OAuth；R7 設定頁 UI 已就緒，按鈕目前無作用）。
2. **使用者活動紀錄**：登入後記錄使用者在 Polaris Desk 做過的事 —— **類似 Claude Code 左側的歷史 session 側欄**：每跑一次研究 / 同業比較留一筆，之後可回去點開重看。
3. （連帶）**訂閱清單** per-user 持久化，與紀錄共用同一儲存後端。

→ 這代表真的需要**使用者身分**（綁紀錄到人）+ 一個**非 `polaris_core` 的寫入庫**（憲法：app 不寫 core）。

### ✅ R2 架構結論

| 決策 | 結論 | 備註 |
|---|---|---|
| **Auth provider** | **Google OAuth** | 專案已在 GCP、評審多半有 Google 帳號；不自刻 auth |
| **Auth 框架** | **NextAuth.js**（前端 Vercel） | 原生支援 Next.js、session 管理完整 |
| **身分驗證層** | app 層驗 JWT（Google JWKS，`aud`=client_id）；用 **`sub`** 當使用者主鍵（**不要用 email**，email 會變） | Cloud Run IAM 維持 `--allow-unauthenticated`，不混 end-user IAM |
| **驗證可繞過** | 無 token → 匿名 / 不記錄 → **保住 token-free CI + 斷網備援**（憲法 V） | Demo / 離線一定要能免登入跑 |
| **儲存後端** | ✅ **Firestore**（2026-06-18 拍板） | GCP 原生、同專案同 billing/IAM、per-user 文件型資料天生適合；**不寫 `polaris_core`**；runtime SA 加 `roles/datastore.user` |
| **紀錄 + 訂閱共用** | history 與 subscriptions **同一個 Firestore**，一次到位 | 避免日後兩次遷移（對應開會議題 A / E） |
| **金鑰** | Google client secret / NextAuth secret → **Secret Manager**（憲法 III），不 commit | |

### 🔶 仍待 R7 / PM 拍板的 2 個子決策
1. **Magic Link 砍不砍**：R7 設定頁另有「工作信箱 Magic Link」UI。**R2 建議 Demo 階段砍掉**（多一條 auth 路徑 + 多一個寄信服務 Resend/SendGrid 的坑，Google OAuth 已足以提供身分）。→ 待 R7 確認。
2. **紀錄深度 A 或 B**：
   - **A. 只記清單 + 重跑**（`{query, page, tickers, time}`，點開重打 API）— R7 localStorage MVP 已是這個。
   - **B. 完整還原**（額外存整包 `answer/evidence/react_steps` → 點開直接還原當時答案）— 真・Claude Code 體驗。
   - **R2 建議**：Demo 走 A（localStorage 撐，後端零改動）；**v1（Demo 後）走 B + Firestore**。

### 時程定位
- **Demo 階段**：維持**免登入** + localStorage 紀錄 MVP → Demo 不擋路、備援路徑單純。
- **Demo 後 v1**：才接 Google OAuth + Firestore（B 級完整還原 + 訂閱）。
- 理由：R7 自己的 UX 評估也把 Auth 列「⚪ 不影響核心分析流程」；真正的 Demo 風險在 R3 端點與 NFR-031，不在 Auth。

### 個資 / 合規（B 級才觸發）
- 存「使用者問過什麼 + 系統答過什麼」= 使用者研究軌跡 → **真實隱私面**：設保留期、嚴格按 `sub` 隔離、答案內容不得跨使用者外洩。NFR-031 不受影響（auth 不碰生成）。

### 待辦
- [x] R2 回覆架構評估（Auth provider / 框架 / 驗證層 / 儲存後端）
- [x] 儲存後端拍板 → **Firestore**
- [ ] R7 確認：Magic Link 砍不砍（建議砍）
- [ ] R7 / PM 確認：紀錄深度 A 或 B（建議 Demo=A、v1=B）
- [ ] （v1）R2 立 Firestore + schema → R3 接 `/history`、`/subscriptions` 端點（或 workflow 結尾自動寫）
- [ ] merge 後把本結論回填 `feature/my-frontend-work_2026_0617` 的開會決策表（議題 A/E + Auth）
