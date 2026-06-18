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
| R7-1 | 帳號登入（Google OAuth）+ 使用者活動紀錄儲存 | R2 | 🟡 排期內（測試 + Demo 皆可用） | ✅ 結論已出（架構拍板） |

> ⚠️ **文件分流提醒**：R7 在 branch `feature/my-frontend-work_2026_0617` 的
> `docs/cross-role-collab/` 下另有更完整的 `R2_需求清單_from_R7.md` 與
> `開會議程_待決策事項_2026-06-18.md`。本節是 **R2 對該需求的架構結論**，
> 待 merge 後應回填進那邊的決策追蹤表（議題 A / E + Auth）。

---

## R7-1 · 帳號登入（Google OAuth）+ 使用者活動紀錄儲存 〔🟡 排期內，測試 + Demo 皆可用〕

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

### ✅ 子決策（2026-06-18 已拍板）
1. **Magic Link** → ❌ **砍**。只做 Google OAuth；設定頁的「工作信箱 Magic Link」UI 移除 / 隱藏，不接寄信服務（省 Resend/SendGrid 一個坑）。
2. **紀錄深度** → **B. 完整還原**。Firestore 每筆 session 存整包 `answer/evidence/react_steps/citations`，點開歷史直接還原當時答案（真・Claude Code 左欄體驗），**不重打 API**。
   - **localStorage** 僅作為**未登入 / 斷網時**的本機降級；登入狀態一律以 Firestore 為準（B 級跨裝置還原）。

> 🔧 **串接做法（給 R7 照著做）**：[`3_給R7的串接指南_Auth_Firestore.md`](./3_給R7的串接指南_Auth_Firestore.md)
> —— 含 NextAuth 設定、後端 JWT 驗證、Firestore 資料模型、`/history`＋`/subscriptions` 端點規格、env 對照、分工。

### 時程定位
- **測試 + Demo 都要能用登入**：Google OAuth + Firestore 在測試期就接起來、登入流程可實際操作；Demo 當天**用登入版**展示（含個人歷史紀錄）。
- **匿名只是降級 fallback**：無 token 時後端走匿名、不寫 Firestore，**僅供 token-free CI 與斷網 / Google 不可達時的備援**（憲法 V），不是預設體驗。
- 真正的 Demo 風險仍在 R3 端點與 NFR-031；Auth 不擋這些，但本身要在測試 / Demo 可用。

### 個資 / 合規（B 級才觸發）
- 存「使用者問過什麼 + 系統答過什麼」= 使用者研究軌跡 → **真實隱私面**：設保留期、嚴格按 `sub` 隔離、答案內容不得跨使用者外洩。NFR-031 不受影響（auth 不碰生成）。

### 待辦
- [x] R2 回覆架構評估（Auth provider / 框架 / 驗證層 / 儲存後端）
- [x] 儲存後端拍板 → **Firestore**
- [x] Magic Link → **砍**
- [x] 紀錄深度 → **B（完整還原）**
- [ ] R7：設定頁移除 / 隱藏 Magic Link UI
- [ ] R2 立 Firestore + schema（per-user session 文件存整包 result）→ R3 接 `/history`、`/subscriptions`（或 workflow 結尾自動寫）→ R7 接 OAuth + 切 Firestore（測試期就接起來、登入版可實操）
- [ ] merge 後把本結論回填 `feature/my-frontend-work_2026_0617` 的開會決策表（議題 A/E + Auth）
