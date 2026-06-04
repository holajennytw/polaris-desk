# 角色規格書（Spec Kit）：R7 — Demo & 全端工程師

**Role**: R7 前端 + 引用 UI + ReAct trace + 上雲部署 **色**：暖橘
**對應**：專題 spec SC-004/005/007；4 週計畫 R7 卡 **Status**: 尚未開工（2026-06-04；開工指南已備、可即刻動）

## 1. Mission
把產品的「臉」做出來並做到能上台：對話 / 引用 UI、報告檢視、Alert Inbox、ReAct trace 視覺化；W4 前端上雲（Vercel 接 Cloud Run）+ Landing + Demo 備援影片。
- **In scope**：前端（Next.js / Chainlit）、引用 UI、Citation Tracer、Report Viewer、Alert Inbox、ReAct trace UI、RWD、Landing、上雲部署（前端）、Demo 影片。
- **Out of scope**：後端 / agent 邏輯（R2/R3）、資料（R4）。

## 2. Deliverables & Acceptance Criteria

| 交付物 | 對應 | 可驗收標準（measurable）|
|---|---|---|
| 對話 + 引用 UI | US1/SC-007 | 能打字提問、看到答案 + 引用；**點引用可跳轉原文出處（Citation Tracer 正確率 100%）** |
| Report Viewer + 匯出 | — | 完整報告檢視頁 + 匯出 PDF |
| Alert Inbox | FR-004 | 合規 / 事件警示收件匣（接 Watchdog；**W2 先用與 R3 約定的 mock 事件 JSON**）|
| ReAct trace UI | FR-004/SC | 能顯示 Deep Research 的**真實** agent 動線（想→查→想）|
| 手機版 RWD | SC-005 | 4 場景畫面在手機 / 電腦皆**無跑版** |
| 前端上雲 + 影片 | G4/SC-005 | 前端部署 Vercel + 接雲端後端；Demo 備援影片定稿、現場切換演練過 |

## 3. Tasks by Week（可勾選）

> **📌 2026-06-04 進度快照（PM 站會）**
> repo 無前端碼、`05_Demo資料` 空 → **尚未開工**。
> - **可即刻開工、不必等後端**：前端吃固定 JSON、用 mock 先行。開工指南 [`../R7_frontend_開工指南.md`](../R7_frontend_開工指南.md)（含三個真實 JSON 契約 + Chainlit/Next.js 選型）。
> - **本週就做**：起 Chainlit 骨架 + mock JSON 做對話/引用 UI。**依賴**：需 thin FastAPI 包 `build_workflow().invoke`（跟 R2 敲，不擋 mock 開發）。
> - 下方任務維持未勾。

**W1**
- [ ] D1 前端骨架（Next.js）能開頁面
- [ ] D2 對話 UI（輸入框 + 訊息泡泡，Chainlit）
- [ ] D3 引用 UI（答案下方顯示來源 / 出處）
- [ ] D4 匯出 PDF
- [ ] D5 G1 驗收（前端面）

**W2**
- [ ] D6 Report Viewer
- [ ] D7 Alert Inbox（**與 R3 約定 Watchdog 事件 mock JSON 契約**）
- [ ] D8 Citation Tracer（點引用跳原文）
- [ ] D9 手機版 RWD
- [ ] D10 G2 驗收（前端面）

**W3（+1 人天）**
- [ ] D11–14 UI polish（量化）：4 場景畫面逐一截圖過 R1 簽核、手機 RWD 無跑版、引用點擊跳轉正確
- [ ] D15 ReAct trace UI 設計
- [ ] D16 ReAct trace UI 實作（接 Deep Research 真實 trace）
- [ ] D17 G3 驗收（前端面）

**W4**
- [ ] D20–22 **前端上雲**：部署 Vercel、接雲端後端（Cloud Run）API；Landing Page 上線（配合 R1 文案）
- [ ] D26 Demo 影片剪輯（場景 4 預錄備援）
- [ ] D27 影片定稿 + mock ReAct trace 接 UI 驗過
- [ ] D28 Demo Day 技術操作手（放影片 / 切備援）

## 4. Dependencies
- **上游**：R3（引用 / Alert / trace 資料格式）、R2（前後端接口 / 上雲後端就緒）、R1（demo 畫面 / 文案需求）、R4（離線備援資料 / mock trace JSON）。
- **下游**：Demo Day 的呈現靠你；斷網切備援也靠你。

## 5. Risks & Fallback
- Watchdog W3 才有 → Alert Inbox W2 先接 **mock 事件 JSON**（與 R3 約定契約），W3 換真資料。
- ReAct trace 真資料未就緒 → 先用 mock trace JSON 接 UI（R4 提供），Demo Day 可切備援。

## 6. Constitution 遵循
- **V**：前端要支援「斷網切本地 + 預錄影片」，且現場切換演練過。
- **II**：引用 UI 是「講得出處」的門面，每句結論都要能點到來源。
