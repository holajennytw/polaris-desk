# Polaris Desk — Antigravity / Gemini 規則

> Google **Antigravity** 與 **Gemini CLI** 讀本檔。
> **完整跨工具守則見 [`AGENTS.md`](./AGENTS.md)（單一事實來源）** —— 本檔只列關鍵紅線，細節以 AGENTS.md 為準。

關鍵紅線：

- 🚀 建環境一鍵：**`make setup`**（建 Python 3.13 venv + 裝依賴 + `.env` 範本）。
- 🐍 開發一律用 **Python 3.13**（`.python-version` 已鎖）。
- 🔴 **NFR-031**：不得產出任何買賣建議。
- 🔑 **金鑰**只放 `.env` / Secret Manager，永不 commit。
- **技術棧**：`google-genai` 新 SDK + `gemini-3-*-preview` + `gemini-embedding-2`（768/cosine）。
- **向量庫**：預設 `VECTOR_BACKEND=bigquery`（共用 `polaris_core`）；pgvector 為離線 fallback，**別改回預設**。寫入只進自己的 `polaris_dev_<name>`、不可寫 `polaris_core`（例外：2026-06-08 起經 PM 同意，R1／R4 帳號 + R4 GCE 預設 SA 有 WRITER 做 ingestion；一般開發者與 agent 仍不可寫，別自行「修正」ACL）。詳見 `docs/開發環境_BigQuery.md`、`docs/協作開發環境_SOP_v1.md` §3.4。
- **不直接推 `main`**：開分支 → PR → 1 人 review → 合。
- 🚦 **GitHub API / 留言節流**：用 `scripts/gh-throttle.sh` 取代裸 `gh`（尤其 `comment` / `create` / `review` / `api -X POST`）；串行 + 呼叫間最小間隔 + rate-limit 自動退避。留言批次化（一 PR 一則），**不要併發跑 `gh`**。背景：2026-06-22 因 API 爆量被暫停帳號。細節見 `AGENTS.md`。
- 🧪 **測試整條流程（UI 未好之前）**：見 [`docs/測試指南_無UI.md`](./docs/測試指南_無UI.md)（CLI / API 優先，標好 🤖 agent 自動 / 🧑 human 必做）。
