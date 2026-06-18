# 引用追蹤器 `GET /chunk/{source_id}` 契約（給 R3）

> 對象：R3（端點實作）+ R4（頁碼 / 可信度資料）。
> 來源：R7 提供的「引用追蹤器」原型（單檔 HTML + 螢幕錄製，2026-06-18）。
> DocViewer 點引用 → 開原始文件、**逐字高亮**、顯示頁碼 / 可信度 /「來源已驗證·未經改寫」。
> 下列契約照原型欄位定死 → R3 實作後，前端 mock 換真 **零重工**。

## Request
```
GET /chunk/{source_id}      # 需 viewer-scoped（chunks 有 owner/confidential 存取控制，同 /ask 的 viewer）
```

## Response
```jsonc
{
  "source_id": "stub-2330-2026Q1-fin",
  "title":      "台積電_2026Q1_合併財報.pdf",   // 文件顯示名
  "doc_type":   "transcript",                  // transcript|major_news|news…
  "kind_label": "財務報表",                     // doc_type→中文顯示（DocViewer 標題列）
  "ticker":     "2330",
  "fiscal_period": "2026Q1",
  "published_at":  "2026-04-18",
  "page":     "p.11",                          // 真實頁碼（見缺口①）
  "trust":    "high",                          // high | mid（可信度標籤；見缺口②）
  "content":  "完整段落原文…",                  // DocViewer 逐行顯示的原文 body
  "highlight":"毛利率 57.8%，營業利益率 47.5%…", // 被引用的片段（= 該 chunk snippet）
  "hl_tokens":["57.8","439,105","47.5"]        // 要高亮的字串（可選；無則前端用 highlight 比對）
}
```
查無 / viewer 無權 → **404**。

## 欄位對應原型
`title`←檔名 · `kind_label`←doc_type 標籤 · `page`←頁碼 · `trust`←可信度 · `content`←body · `highlight`←擷取片段 · `hl_tokens`←要高亮的 token · `source_id`←source_id。

## ⚠️ 兩個資料缺口（R3 + R4 先確認）
1. **真實頁碼 `page`**：BQ `chunks` 文字片段目前**未必有 `page_num`**（整頁向量 `colpali_pages` 才有）。
   → R4 確認；若無，回 `null`，前端顯示「頁碼未提供」（DocViewer 仍可顯示原文 + 片段）。
2. **可信度 `trust` 規則**：現無此欄，需**定義**。建議：依 `doc_type` 權威性 + rerank 分數分箱（`high`/`mid`）；
   過渡期可先固定 `high`，但要 log 為暫定。

## 不變量
- `chunks` **不可前端裸查**（owner/confidential）→ 一律經此端點 viewer 過濾後回。
- 走 retriever 取該 `source_id` 的 chunk 原文（不直連 BQ）。
- 欄位名鎖定，改契約＝R3/R7（/R4）一起改。
