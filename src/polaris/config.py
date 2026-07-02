"""唯一設定來源 —— 全部從 .env 讀進來。

雲端與本地用同一份程式，差別只在 .env（或雲端環境變數）。
預設後端為 BigQuery（共用 canonical）；pgvector 為離線 fallback——換後端只改 VECTOR_BACKEND。
"""
from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- 向量庫後端開關（雲端 ↔ 本地就靠這個）---
    vector_backend: str = "bigquery"          # bigquery（預設）| pgvector（離線 fallback）

    # 雲端 BigQuery（預設後端）
    gcp_project: str = "polaris-desk-team"
    bq_dataset: str = "polaris_core"          # 共用唯讀 canonical
    dev_dataset: str = ""                     # 個人 scratch（polaris_dev_<name>）；寫入走這裡
    # 憲法 III / SOP §3.4：polaris_core 預設唯讀（client 端防呆，不取代 server ACL）。
    # 只有經 PM 同意的 ingestion 帳號（R1/R4，2026-06-08 起）設 BQ_ALLOW_CORE_WRITE=1。
    bq_allow_core_write: bool = False

    # 本地 pgvector（離線 fallback）
    database_url: str = "postgresql://polaris:polaris@localhost:5432/polaris"

    # LLM / 檢索金鑰（可留空，跑骨架測試不需要）
    gemini_api_key: str = ""
    cohere_api_key: str = ""
    tavily_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # 模型（名稱對齊 google-genai 當前版本）
    gemini_model_pro: str = "gemini-3-pro-preview"
    gemini_model_flash: str = "gemini-3-flash-preview"
    embedding_model: str = "gemini-embedding-2"   # 最新多模態嵌入；純文字可改 gemini-embedding-001
    embedding_dim: int = 768

    # Vertex AI（用 GCP 專案配額 / trial credit 跑「生成」，繞過 AI Studio 免費日配額）。
    # embeddings 一律仍走 api_key 同一模型，以保 polaris_core 既有 768 向量空間（別動）。
    gemini_use_vertex: bool = False           # GEMINI_USE_VERTEX=1 → 生成走 Vertex（ADC / SA 認證）
    vertex_location: str = "global"           # gemini-3-flash-preview 僅 global 端點可用（實測 2026-06-16）

    # LLM 成本 / 資源護欄（LLM10）
    llm_max_output_tokens: int = 4096         # 每次生成輸出上限（傳給 Gemini，擋失控長輸出）
    llm_token_budget: int = 0                 # process 累計 token 上限；0 = 無上限（預設）

    # 通知中心（specs/002）：內部 Slack incoming webhook。金鑰規則同憲法 III——
    # 只放 .env / Secret Manager，永不 commit；留空 = channel 自動停用（0 外呼）。
    slack_webhook_url: str = ""

    # 通知事件「生產者」端點（POST /notifications/events、/notifications/reset）的內部
    # 共享密鑰（security review #2）。生產者帶 `X-Polaris-Notify-Token` header，後端常數
    # 時間比對。金鑰規則同憲法 III（只放 .env / Secret Manager，永不 commit）。
    #   • 有設密鑰 → 一律要求相符，否則 401。
    #   • 沒設密鑰 + app_env=="cloud" → fail closed（503）：prod 生產者端點未設定即拒收，
    #     絕不在雲端默默接受匿名事件。
    #   • 沒設密鑰 + 非 cloud（local / CI / demo）→ 放行，保 token-free 開發與互動 demo。
    notifications_producer_token: str = ""

    # 應用
    app_env: str = "local"                    # local | cloud
    log_level: str = "INFO"
    top_k: int = 8

    # --- app 層限流（security review #4：匿名成本型 DoS 護欄）---
    # /ask /research 每「來源 key」（XFF / 對端 IP）每 60s 上限。**只在
    # app_env=="cloud" 生效**（local / CI / demo 不限流，保 token-free 開發）；
    # 設 0 = 關閉。配合 Cloud Run --max-instances → 全域成本天花板有界。
    rate_limit_per_min: int = 20

    # --- 輸入端守門（防止使用者亂問；2026-07-02）---
    # 預設關：screen_query() 一律放行、workflow no-evidence 邊不掛 → prod / CI 行為零變動。
    # 設 INPUT_GATE=1 才啟用：L1 注入攔截 + L2 範圍分流（floor + Gemini Flash smart）
    # + L3「查無足夠來源」短路（calculator 後 contexts 仍空 → 不生成、回固定訊息）。
    input_gate: bool = False
    # L0 每人每日提問配額（成本 / 洗版護欄）。0 = 關閉（預設）。keyed on 登入身分 sub，
    # 匿名 keyed on client IP。**只在 app_env=="cloud" 生效**（同 rate_limit_per_min）。
    daily_question_quota: int = 0

    # --- Vision-OCR ingestion（圖表/掃描頁→文字，spec 2026-06-23）---
    # 預設關：active_vision_extractor() 回 None → CI 0 外呼、不 import genai/pymupdf。
    # 設 VISION_EXTRACTION=1 + 裝 .[vision] 才啟用（離線 ingestion 用）。
    vision_extraction: bool = False
    vision_confidence_floor: float = 0.6

    # --- visual_reader 節點（Phase B：查詢期 vision 讀圖 escalation）---
    # 預設關：節點 no-op、prod 行為零變動。設 VISUAL_READER=1 + VISION_EXTRACTION=1
    # 才啟用（看圖題且檢索文字缺數字時，render 被引用頁 → vision 讀圖補脈絡）。
    visual_reader: bool = False
    # 觸發靈敏度（交由 eval 校準，specs/004）：看圖題的檢索脈絡「無數字比例」≥ 此值才升級。
    # 1.0=全部脈絡無數字才升級（最保守）；調低→更積極。
    visual_reader_numberless_floor: float = 1.0
    # 查詢期頁圖來源：源 PDF 語料根目錄（本地路徑或 gs://bucket/prefix）。
    # 依真實檔名慣例 {ticker}_*_{period}_concall_presentation.pdf 遞迴解析（見
    # scripts/vision_ingest_pilot.py）。空 / 找不到 → 節點 no-op。prod 需把 corpus
    # 掛載到本地或 staged 到 GCS（目前無持久 PDF 庫，pilot 用本地 data/）。
    pdf_corpus_dir: str = ""

    # --- ColPali 第 4 路 query 端編碼器（#133）---
    # 預設關閉：active_colpali_query_fn() 回 None → 第 4 路關閉、CI 0 import / 0 下載。
    # 設 COLPALI_QUERY_ENCODER=1 才載入 colpali-engine + torch + 權重（~5GB，需 GPU）。
    # model / pool 必須與 R4 page 端（colpali_pages，patch mean-pool 成 128 維）同空間。
    colpali_query_encoder: bool = False
    colpali_model: str = "vidore/colpali-v1.2"
    colpali_device: str = ""                  # ""=自動（cuda 優先，否則 cpu）；可設 cuda / cpu

    # R7 前端跨域（CORS）允許來源；逗號分隔。預設本地 dev（Next.js 3000 / Chainlit 8501）；
    # 雲端設成 R7 的 Vercel 網域。env 同時收 `POLARIS_CORS_ORIGINS`（runbook / .env.example /
    # Cloud Run 部署指令用）與 `CORS_ORIGINS`（API 使用指南用）——兩個歷史名稱都吃，避免
    # 設了卻被 `extra="ignore"` 默默丟掉、CORS 仍停在 localhost 而擋掉 Vercel 前端。
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8501",
        validation_alias=AliasChoices("POLARIS_CORS_ORIGINS", "CORS_ORIGINS", "cors_origins"),
    )

    # 使用者登入（R7-1：Google OAuth + Firestore 活動紀錄）。後端只需 client_id 驗
    # id_token 的 aud；client secret 留前端（NextAuth）。留空 = 任何 token 都驗不過 →
    # 全程匿名（token-free CI / 斷網降級照常）。Firestore 認證走 ADC（runtime SA），免金鑰。
    google_client_id: str = ""

    # --- 多金鑰輪替（429 配額耗盡時換把金鑰）---
    # GEMINI_API_KEY / COHERE_API_KEY 支援逗號分隔多把金鑰（單把無逗號 = 1 元素，
    # 向後相容）。429 時 client 端自動輪到下一把；全數耗盡才由 retry 退避重試。
    @property
    def gemini_api_keys(self) -> list[str]:
        return _split_keys(self.gemini_api_key)

    @property
    def cohere_api_keys(self) -> list[str]:
        return _split_keys(self.cohere_api_key)


def _split_keys(raw: str) -> list[str]:
    """逗號分隔字串 → 金鑰 list；去空白、丟空字串與 ``#`` 開頭佔位。"""
    keys: list[str] = []
    for part in raw.split(","):
        stripped = part.strip()
        if stripped and not stripped.startswith("#"):
            keys.append(stripped)
    return keys


# 全域單例 —— 其他模組 `from polaris.config import settings`
settings = Settings()
