# 安全強化 — 上線門檻（external code review 後續）

> 外部 code review（2026-06）找出 4 項，已修補並上線（rev `polaris-api-00023`）。
> 本文記錄**尚未實作**的兩項——皆涉及基礎設施或產品決策，不宜由程式碼預設值默默改線上行為，
> 故留為待辦 + 實作方案，待 PM / R2 拍板。
>
> 已完成（供對照）：#1 viewer ACL 改後端推導、#2 通知生產者密鑰守門、#3 輸入字數/大小上限、
> #4 `DELETE /history`。詳見 PR #57 與部署紀錄。

---

## 待決策（產品）— 先回答這兩題，下面才好定案

1. **`/ask`、`/research` 是否設計為 production 匿名可用？**
   現況：匿名（無 Bearer）→ 200（憲法 V 的斷網/ token-free 降級保命路徑）。若對外正式開放，
   匿名流量會直接觸發 LLM / 檢索成本，需在上線門檻補「匿名額度 + 成本熔斷 + IP 節流」。
2. **`viewer` ACL principal 的正確語意？**
   現況：後端取 Google `sub`（與 `/history` 同主鍵）。若應為「公司租戶 ID」而非個人 `sub`，
   需加一層 server-side `sub → tenant` 對應（單點修改 `_viewer_for`，可逆）。

> `polaris_core.chunks` 目前 **owner 全 NULL、confidential 全 FALSE**（10,641 列，2026-06-27 驗證）
> → #1 當前為 latent（無 owner-scoped 資料可外洩）。修補為**預防性**：owner-scoped ingestion
> 進場前先就位即可，不急於本週。

---

## A. 匿名 `/ask`·`/research` 成本/濫用護欄（review #3 的延伸）

**問題**：`max_length` 只擋單一請求的輸入大小，擋不住「大量請求」造成的 LLM 成本型 DoS。

**方案（由輕到重，建議分階段）**：

1. **行程級 token 預算熔斷（最低成本，今天就能上）**
   `polaris/config.py` 已有 `llm_token_budget`（行程累計 token 上限，預設 `0`=無上限）與
   `llm_max_output_tokens`。上線時設一個非零 `LLM_TOKEN_BUDGET`，到頂後拒新生成（graceful）。
   - 限制：每個 Cloud Run instance 各自計數，**自動擴容下是 per-instance 上限**，非全域。
   - 適合「單機失控保護」，不是「全域配額」。
2. **全域配額 / IP 節流 → 基礎設施層**（見 §B；in-app 在多 instance 下無效，別自欺）。
3. **匿名 vs 登入分流**：可考慮匿名只走較便宜的 fallback / 較小 `top_k`，登入才給完整檢索。
   需配合決策 #1。

**驗收**：壓測下成本可預期；到頂回 429/503（非 500）；`/health` 不受影響。

---

## B. Cloud Armor 速率限制（review #2/#3 的基礎設施層）

**為什麼不做在 app 內**：Cloud Run 自動擴容，in-process limiter 各 instance 獨立計數，
對分散式洪水無效（會給「有保護」的錯覺）。速率限制要在**進入點**做。

**前置事實**：Cloud Run 的預設 `*.run.app` URL **不**支援 Cloud Armor。需在前面架
**External HTTPS Load Balancer + Serverless NEG**，把 Cloud Armor security policy 掛上 backend service。

**實作步驟（asia-east1，沿用 SA `polaris-run@`）**：
```bash
# 1) Serverless NEG 指向 Cloud Run 服務
gcloud compute network-endpoint-groups create polaris-api-neg \
  --region=asia-east1 --network-endpoint-type=serverless \
  --cloud-run-service=polaris-api

# 2) backend service + 掛 NEG
gcloud compute backend-services create polaris-api-be --global \
  --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend polaris-api-be --global \
  --network-endpoint-group=polaris-api-neg --network-endpoint-group-region=asia-east1

# 3) Cloud Armor 速率限制 policy（範例：每 IP 每分鐘 60 req，超量 429）
gcloud compute security-policies create polaris-ratelimit
gcloud compute security-policies rules create 1000 \
  --security-policy=polaris-ratelimit \
  --expression="true" --action=rate-based-ban \
  --rate-limit-threshold-count=60 --rate-limit-threshold-interval-sec=60 \
  --conform-action=allow --exceed-action=deny-429 \
  --enforce-on-key=IP --ban-duration-sec=120
gcloud compute backend-services update polaris-api-be --global \
  --security-policy=polaris-ratelimit

# 4) URL map + HTTPS proxy + managed cert + forwarding rule + 靜態 IP
#    （略；標準 LB 組裝。需一個網域指向保留的靜態 IP 供 managed cert 簽發。）
```

**重大影響（決策點）**：
- **進入點 URL 改變**：使用者 / 前端 `BACKEND_API_URL` 要改指 LB 網域（非 `*.run.app`）。
  managed cert 需網域 + DNS 指向 LB IP，憑證簽發要時間。
- 可考慮把 Cloud Run 設成**只接受來自 LB 的流量**（`--ingress=internal-and-cloud-load-balancing`），
  否則 `*.run.app` 直連會繞過 Cloud Armor。
- 成本：LB + 靜態 IP 有固定月費。

**建議**：若短期內只需「擋洪水」，先上 §A.1 行程級熔斷 + Cloud Run 並行/最大 instance 上限
（`--concurrency` / `--max-instances`）當成本天花板；待對外正式開放（決策 #1=是）再投資 §B 的 LB+Armor。

---

## 落地順序建議
1. PM 回決策 #1 / #2。
2. 設 `--max-instances` + `--concurrency`（成本硬天花板，零程式碼，先做）。
3. 若決策 #1=是 → 上 §A.1 token 熔斷 + §B Cloud Armor LB。
4. 若 `viewer` 應為租戶 → 改 `_viewer_for` 加 `sub→tenant` 對應，並回填 ingestion 的 `owner`。
