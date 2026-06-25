# Polaris Desk — 軟體架構 / 資料流程 / 使用者流程

> 本文件依 `src/polaris/` 與 `frontend/src/` 實際程式碼（import 圖、API 路由、前端 hooks）整理。
> **視覺處理：ColPali 退役為兩段** ——
> ① **入庫期**：Vision-OCR 抽圖表文字進索引（`ingestion/vision_*`, gated `VISION_EXTRACTION`）。
> ② **查詢期**：`graph/nodes/visual_reader.py` Phase B escalation（gated `VISUAL_READER`，預設關）。
> eval 場景 3 已改走文字 workflow（`_run_visual` 已移除）；`colpali_*` 模組軟退役（保留檔案，
> 因 R4 #133 query encoder 剛建出，硬刪需與 R4/PM 對齊）。

---

## 0. 模組依賴分層（verified import graph）

```mermaid
flowchart TB
    subgraph L0["基礎層"]
        CFG["config.py"]
        RETRY["retry.py"]
    end

    subgraph L1["LLM / 向量 / 壓縮"]
        BUD["llm/budget.py"]
        GEM["llm/gemini.py"]
        TOK["compression/tokens.py"]
        COMPR["compression/compressors.py"]
        VBASE["vectorstore/base.py"]
        VFAC["vectorstore/factory.py"]
        VBQ["bigquery_store"]
        VPG["pgvector_store"]
        VCP["colpali_store (legacy)"]
    end

    subgraph L2["graph 核心型別 / 提示 / 工具"]
        STATE["graph/state.py — ResearchState (中樞型別)"]
        PROMPTS["graph/prompts.py"]
        COMPLI["graph/compliance.py"]
        REDACT["graph/redaction.py"]
        TEMPORAL["graph/temporal.py"]
    end

    subgraph L3["節點 / 檢索"]
        TRACE["nodes/trace.py"]
        PLAN["nodes/planner_agent.py"]
        WRITE["nodes/writer_agent.py"]
        CAGENT["nodes/compliance_agent.py"]
        STUBS["nodes/stubs.py (wiring 真 agent)"]
        RETR["retrieval/retriever.py — HybridRetriever"]
    end

    subgraph L4["編排 / 專用 agent"]
        WF["graph/workflow.py — 5 節點"]
        DR["graph/deep_research/* — ReAct"]
        WD["graph/watchdog/* — MOPS"]
        NEWS["graph/news/* — 新聞卡"]
    end

    subgraph L5["服務 / 入庫 / 評測 / 日報"]
        NOTIF["notifications/* — service 七關"]
        INGEST["ingestion/* — chunker+pipeline"]
        EVAL["eval/* — Ragas 管線"]
        DAILY["daily_status/* — GitHub 日報"]
    end

    subgraph L6["對外 / 儲存"]
        API["api.py — FastAPI"]
        AUTH["auth.py — Google OAuth"]
        SSTORE["structured_store.py → BigQuery"]
        USTORE["user_store.py → Firestore"]
        SERVER["server.py"]
    end

    RETRY --> GEM
    CFG --> BUD --> GEM
    TOK --> GEM
    VBASE --> VFAC
    VFAC --> VBQ & VPG & VCP
    STATE --> TEMPORAL & RETR & NOTIF
    PROMPTS --> PLAN & WRITE & CAGENT
    GEM --> STUBS & RETR & DR & INGEST
    COMPR --> WRITE
    STUBS --> WF
    RETR --> STUBS & DR
    WF --> DR & EVAL
    WD --> NOTIF
    VFAC --> RETR & INGEST
    API --> WF & DR & WD & NOTIF & RETR & SSTORE & USTORE & AUTH & SERVER
    EVAL --> WF & DR
```

---

## 1. 軟體架構（系統全貌）

```mermaid
flowchart TB
    subgraph Client["🖥️ Frontend — Next.js (frontend/)"]
        UI["Dashboard + polaris/ 元件<br/>KpiCard / CitationList / ComplianceBanner<br/>ReActTrace / AlertItem / DocViewer"]
        Hooks["hooks/ — useAsk useResearch useAlerts<br/>useNotifications useFinancials useCompanies<br/>useSubscriptions useUnread"]
        ApiLib["lib/api.ts — 唯一資料存取層 (+ mocks fallback)"]
        UI --> Hooks --> ApiLib
    end

    subgraph API["⚙️ Backend — FastAPI (api.py)"]
        AUTH["auth.py — Google OAuth (current_user)"]
        RR["/ask · /research"]
        RW["/alerts"]
        RN["/notifications · /notifications/events · /{id}/read"]
        RS["/companies · /financials · /events"]
        RU["/history · /subscriptions"]
        ROPS["/health · /healthz"]
    end

    subgraph Core["🧠 Core (src/polaris/)"]
        WF["graph/workflow.py — 5 節點<br/>Planner→Retriever→Calculator→Writer→Compliance"]
        DR["graph/deep_research — ReAct agent (同業比較)"]
        WD["graph/watchdog — MOPS 事件 agent"]
        NEWS["graph/news — 新聞卡"]
        RETR["retrieval/retriever — HybridRetriever (3 路)"]
        LLM["llm/gemini — google-genai · gemini-3-*-preview<br/>budget 金鑰輪替"]
        COMP["compression — context 壓縮 (writer 用)"]
        NOTIF["notifications — service 七關 + inbox + channels"]
        DAILY["daily_status — GitHub 日報"]
        ING["ingestion — chunker + Vision-OCR + embed"]
    end

    subgraph VS["🗄️ VectorStore 抽象 (vectorstore/)"]
        FAC["factory.get_vector_store() ← VECTOR_BACKEND"]
        BQ["BigQueryStore (預設)"]
        PG["PgVectorStore (離線/Demo)"]
        FAC --> BQ & PG
    end

    subgraph Ext["☁️ Data / External"]
        CORE[("BigQuery polaris_core<br/>chunks 768-dim · financial_metrics<br/>company_dim · 語意 views")]
        DEV[("polaris_dev_&lt;name&gt; scratch")]
        FS[("Firestore — history / subscriptions")]
        PGDB[("Postgres + pgvector")]
        GEMAPI["Gemini API / Vertex AI"]
        COH["Cohere Rerank"]
        GH["GitHub API"]
        MOPS["公開資訊觀測站 / MOPS"]
    end

    ApiLib -->|HTTPS JSON| API
    RR --> WF & DR
    RW --> WD
    RN --> NOTIF
    RS --> SST["structured_store → BigQuery"]
    RU --> UST["user_store → Firestore"]
    WF --> RETR --> FAC
    RETR --> COH
    WF --> COMP
    WF & DR & WD & NEWS & ING --> LLM --> GEMAPI
    BQ --> CORE & DEV
    PG --> PGDB
    SST --> CORE
    UST --> FS
    DAILY --> GH
    WD --> MOPS
    ING --> FAC
```

---

## 2. Ingestion 資料流（含 Vision-OCR）

```mermaid
flowchart LR
    PDF["法說會 PDF / 財報"] --> EXP["ingestion/chunker.extract_pages<br/>(pypdf)"]
    EXP --> HAS{"頁有文字層?"}
    HAS -->|有| CHK["chunk_pages — 頁為錨<br/>id={ticker}-{period}-pNNN-cNNN"]
    HAS -->|"無 (圖片頁)"| VIS["🆕 Vision-OCR 抽取<br/>(Approach A · gated VISION_EXTRACTION)<br/>gemini-3-preview Vertex · --throttle"]
    VIS --> CHK
    CHK --> SAN["sanitize.sanitize_text"]
    SAN --> PIPE["pipeline.ingest_chunks<br/>_to_document + embed"]
    PIPE --> EMB["llm/gemini embed<br/>gemini-embedding-2 · 768-dim · cosine<br/>(需 GEMINI_API_KEY)"]
    EMB --> FAC["vectorstore factory"]
    FAC --> DEV[("polaris_dev_&lt;name&gt; (一般開發者)")]
    FAC -.->|"R1/R4 經 PM 同意"| CORE[("polaris_core")]

    classDef new fill:#1e4d3a,stroke:#3ad98a,color:#fff
    class VIS new
```

> 舊行為：無文字層頁「誠實跳過」。新行為：交給 Vision-OCR 抽成文字 chunk，納入同一 768-dim 向量空間，檢索期不需單獨視覺路。

---

## 3. RAG 檢索資料流（`/ask` · `/research`）

```mermaid
flowchart LR
    Q["使用者問題"] --> WF{{"LangGraph workflow"}}
    WF -->|"planner 抽 filters<br/>(company / doc_type)"| RETR

    subgraph RETR["🔎 HybridRetriever.retrieve() — 3 路"]
        direction TB
        BM["① BM25 keyword (rank_bm25)"] --> MRG["_merge_results 去重+合併 channels"]
        VEC["② Vector — embed query → VectorStore.search"] --> MRG
        MRG --> RRK["③ Cohere Rerank (rerank-v3.5 · opt-in)"]
    end

    VEC --> FAC["VECTOR_BACKEND"]
    FAC --> BQ[("polaris_core")]
    FAC -.fallback.-> PG[("pgvector")]
    RRK --> CITE["帶 Citation 的 SearchResult<br/>(page 接地 · 含 Vision-OCR 抽出的圖片頁文字)"]
    CITE --> CALC["Calculator — 財務數字"]
    CALC --> WRT["Writer — context 壓縮 → Gemini 生成 + 引用"]
    WRT --> CMP["Compliance — NFR-031 不得產出買賣建議"]
    CMP --> ANS["答案 + 引用清單 + ReAct trace"]
```

---

## 4. LangGraph 工作流 + 專用 agent

```mermaid
flowchart TB
    START(["invoke(query)"]) --> P["planner<br/>planner_agent.make_plan"]
    P -->|continue| R["retriever<br/>HybridRetriever 3 路"]
    R -->|continue| V["🆕 visual_reader<br/>(Phase B escalation, flag VISUAL_READER)<br/>看圖題且脈絡缺數字 → render 頁圖 → vision 讀圖<br/>never halts · 預設關 = no-op"]
    V --> C["calculator<br/>財務計算"]
    C -->|continue| W["writer<br/>壓縮 context + writer_agent.make_draft"]
    W -->|continue| CM["compliance<br/>compliance_agent.review (NFR-031)"]
    CM --> E([END])

    P -.->|"halt / 例外"| T
    R -.->|halt| T
    C -.->|halt| T
    W -.->|halt| T
    T["terminal — 固定錯誤訊息<br/>compliance_status=unknown"] --> E

    classDef biz fill:#1e3a5f,stroke:#4a90d9,color:#fff
    classDef infra fill:#5f1e1e,stroke:#d94a4a,color:#fff
    classDef new fill:#1e4d3a,stroke:#3ad98a,color:#fff
    class P,R,C,W,CM biz
    class T infra
    class V new
```

> **Phase B escalation chain（非並行路）**：`retriever → visual_reader → calculator → writer`。
> visual_reader 是 best-effort 加分節點：`VISUAL_READER` flag 預設關 → no-op；開啟且
> 看圖題的檢索脈絡缺數字時，render 被引用頁丟給 gemini vision 讀圖、攤平成文字脈絡補進
> contexts（origin=vision）。取不到頁圖 / 抽取空白 / 任何外呼失敗 → no-op，never halts、不編造。
> 查詢期 PDF 來源（`pdf_corpus_dir` 本地慣例，GCS/Drive 取檔為 TODO）與觸發門檻（eval 校準）為待整合點。

```mermaid
flowchart LR
    subgraph DR["Deep Research (ReAct · 同業比較)"]
        DRQ["問題"] --> DEC["_decide (Thought→Action)"]
        DEC --> ACT["_act → search → Citation"]
        ACT -->|"未達 min_citations"| DEC
        ACT -->|"足夠 / exhausted"| SYN["_synthesize (帶引用)"]
    end
    subgraph WD["Watchdog (MOPS)"]
        EV["MopsEvent"] --> SUM["_smart_summary (Gemini + fallback)"]
        SUM --> EVI["_build_evidence → Citation"]
        EVI --> AL["WatchdogAlert → watchdog/notify"]
        AL --> NS["notifications.service.publish"]
    end
```

---

## 5. 通知中心：`publish()` 七道關卡（notifications/service.py）

```mermaid
flowchart TD
    P["生產者 service.publish(event)<br/>(Watchdog / workflow / news)"] --> V{"① validate"}
    V -->|ValidationError| RJ1(["rejected — 壞事件不弄垮管線"])
    V -->|ok| D{"② 去重 is_duplicate"}
    D -->|是| RJ2(["deduped — exactly-once"])
    D -->|否| G{"③ 接地檢查<br/>user 且無 evidence?"}
    G -->|無來源| RJ3(["rejected — 沒來源不發"])
    G -->|有來源/internal| C{"④ Compliance Gate<br/>audience=user?"}
    C -->|internal| SKIP["compliance_status=skipped"]
    C -->|user → review| CR{"blocked?"}
    CR -->|blocked| INC["_make_incident 事故通知<br/>(不引用被攔原文)"] --> DLV1["_deliver"] --> RJ4(["blocked — incident filed"])
    CR -->|passed| PASS["passed"]
    SKIP --> B["composer.build"]
    PASS --> B
    B --> S{"⑤ 訂閱過濾 allows?<br/>(alert 恆放行)"}
    S -->|被濾| RJ5(["filtered"])
    S -->|放行| DG{"⑥ digest 同鍵?"}
    DG -->|有→merge| MRG(["digested"])
    DG -->|無| DLV["⑦ _deliver"]
    DLV --> INBOX["inbox.add (恆入收件匣)"]
    INBOX --> EXT{"audience=internal?"}
    EXT -->|是| CH["SlackWebhookChannel.send"]
    CH -->|失敗| FAIL["inbox.record_failure (降級, 不拋)"]
    EXT -->|否| OUT(["delivered"])
    CH --> OUT

    classDef reject fill:#5f1e1e,stroke:#d94a4a,color:#fff
    classDef ok fill:#1e5f2e,stroke:#4ad96a,color:#fff
    class RJ1,RJ2,RJ3,RJ4,RJ5 reject
    class OUT,MRG ok
```

---

## 6. 使用者流程（User Flow）

```mermaid
flowchart TD
    L["開啟 polaris-web (Cloud Run)"] --> AU{"已登入?"}
    AU -->|否| OAuth["Google OAuth (auth.py)"]
    OAuth --> DASH
    AU -->|是| DASH["Dashboard"]
    DASH --> CH{"操作"}

    CH -->|提問| ASK["useAsk → POST /ask"]
    ASK --> RES["答案 + CitationList<br/>+ ComplianceBanner + ReActTrace"]
    RES --> CITE["點引用 → DocViewer 查原文"]
    RES --> SAVE["存 /history (Firestore, 依 uid)"]

    CH -->|深度研究| DRP["useResearch → POST /research → ReportModal"]
    CH -->|看快訊| ALV["useAlerts → GET /alerts (Watchdog)"]
    CH -->|通知中心| NT["useNotifications → GET /notifications<br/>標已讀 POST /{id}/read"]
    CH -->|訂閱個股| SUB["useSubscriptions → GET/POST /subscriptions"]
    SUB -.->|觸發監看| ALV
    CH -->|財務/公司/新聞| ST["useFinancials / useCompanies<br/>GET /financials /companies /events → KpiCard"]
```

---

## 關鍵設計重點（verified）

| # | 重點 | 程式落點 | 為什麼 |
|---|------|----------|--------|
| 1 | **單一切換點換後端** | `vectorstore/factory.py` ← `VECTOR_BACKEND` | BigQuery（預設/共用 `polaris_core`）↔ pgvector（離線 Demo），程式不動只改一個 env |
| 2 | **檢索純 3 路** | `retrieval/retriever.py` | BM25 + 向量 + Cohere rerank；視覺內容改在 ingestion 用 **Vision-OCR** 抽成文字，**ColPali 第 4 路退役** |
| 3 | **合規硬約束貫穿兩條路** | workflow `compliance` 節點 + notifications 第④關 | 落實 NFR-031；研究答案與 user 通知都必審，被攔不外洩原文 |
| 4 | **引用接地 = 發送前提** | Retriever 帶 `Citation` + notifications 第③關 grounding | 沒來源的 user 事件 `rejected`；Writer 壓縮 context 但 citations 不受影響 |
| 5 | **介面/實作分離（注入式 seam）** | `nodes/stubs.py`、`Channel` Protocol、Deep Research `search` | wiring 不動換實作；測試可 monkeypatch 單一節點/管道 |
| 6 | **儲存分流** | `structured_store→BigQuery`、`user_store→Firestore` | 結構化財報走 BQ；個人 history/訂閱走 Firestore，前端不直連資料庫 |
| 7 | **publish 永不對生產者拋例外** | `notifications/service.py` | 六態 `DeliveryStatus`（delivered/deduped/digested/blocked/filtered/rejected）+ channel 失敗降級記錄 |
