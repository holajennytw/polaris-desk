<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/004-eval-pipeline/spec.md`
<!-- SPECKIT END -->

# Polaris Desk — 給 coding agent 的專案守則

> 跨工具單一事實來源＝ [`AGENTS.md`](./AGENTS.md)（Codex / Antigravity / Cursor 讀它）。
> 本檔為 **Claude Code** 鏡像；改規則時請同步 `AGENTS.md`（與 `GEMINI.md`）。

**權威規格**：repo 內 `.specify/memory/constitution.md`（憲法）；團隊完整規格在
Google Drive `Polaris Desk/03_規格書_PRD/spec-kit/`（專題 spec + 7 角色 spec）。

**硬約束（憲法，違反 = No-Go）**：
- 🔴 **NFR-031**：不得產出任何買賣建議（投顧執照風險）。
- 🔑 **金鑰**只放 `.env` / Secret Manager，永不 commit（`.env` 已 gitignore）。
- **引用接地**：每句結論 / 每個數字都要有來源。
- **技術棧**：`google-genai` 新 SDK + `gemini-3-*-preview` + `gemini-embedding-2`（768/cosine），**非**舊版 `google-generativeai`。
- **向量庫**：**預設 `VECTOR_BACKEND=bigquery`**（共用 canonical `polaris_core`，2026-06-02 起）；pgvector 為離線 / Demo fallback（一個 env 切換，**別改回預設**）。寫入只進自己的 `polaris_dev_<name>`、**不可寫 `polaris_core`**（例外：2026-06-08 起經 PM 同意，R1／R4 帳號 + R4 GCE 預設 SA 有 `polaris_core` WRITER 做 ingestion；一般開發者與 agent 仍不可寫，且 schema/index 變更一律走 SOP §7 PR — 別自行「修正」這份 ACL）；pgvector fallback 查詢用 `<=>`。詳見 `docs/開發環境_BigQuery.md`、`docs/協作開發環境_SOP_v1.md` §3.4。
- **🐍 Python 3.13**：開發 / CI 一律用 **Python 3.13**（已鎖在 `.python-version`，`pyproject.toml` 也設 `requires-python>=3.13`）。建環境：`uv venv --python 3.13 && uv pip install -e ".[dev]"`。**不要**用其他版本起 venv。

**🚦 GitHub API / 留言節流（必守）**：**用 `scripts/gh-throttle.sh` 取代裸 `gh`**，尤其是會產生內容的呼叫（`comment` / `create` / `review` / `api -X POST…`）。它串行、強制呼叫間最小間隔（mutating 預設 5s、跨多次呼叫也算）、遇 secondary rate limit 自動退避重試、並寫 log（`scripts/gh-throttle.sh --audit` 可查）。**留言批次化**：一個 PR / issue 只發一則彙整留言；**不要平行 / 併發**跑多個 `gh`。背景：2026-06-22 因 API + 留言爆量被 GitHub 判定違反 ToS、暫停帳號（已申訴）；節流是為復權後不再觸發。細節以 [`AGENTS.md`](./AGENTS.md) 為準。

**🧪 測試整條流程（UI 未好之前）**：見 [`docs/測試指南_無UI.md`](./docs/測試指南_無UI.md) —— CLI / API 優先，標好「🤖 agent 可自動跑」與「🧑 human 必做」（填金鑰 / `gcloud` 登入 / `DEV_DATASET` 改名），每步附預期輸出。要我幫忙建測試環境就說「依 `docs/測試指南_無UI.md` 執行」。

**Spec Kit 指令**：`/speckit-constitution`、`/speckit-specify`、`/speckit-plan`、`/speckit-tasks`、`/speckit-implement`（選用：`/speckit-clarify`、`/speckit-analyze`、`/speckit-checklist`）。
