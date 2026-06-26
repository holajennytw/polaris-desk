# R6 Phase 2 Formal-Scope QA Run - 2026-06-26

> This is a Phase 2 formal-scope QA run with final QA readiness verdict. It is not an automatic final QA pass.

## 1. 本輪定位

- Phase 2 Formal-Scope QA Run
- Not automatic final QA pass
- Final QA readiness verdict included
- Full 20-question run against currently deployed Cloud Run `/ask` service

## 2. Environment / Deployment Traceability

- Endpoint: `https://polaris-api-14326813937.asia-east1.run.app`
- Local repo: `polaris-desk`
- Local git: `8c32bb5` `Merge pull request #44 from holajennytw/docs/gemini-grounding-touchpoints`
- Health HTTP: `200`
- Health response: `{"status": "ok", "service": "polaris-desk", "app_env": "cloud", "vector_backend": "bigquery"}`
- deployment_version: `unknown`

R6 cannot verify whether Cloud Run is deployed to the latest backup/main. This run should be interpreted as a formal-scope QA run against the currently deployed Cloud Run service.

## 3. Architecture Alignment Note

- 根據最新 `docs/architecture.md`，`/ask` 主線仍是 Planner → Retriever → Calculator → Writer → Compliance。
- Retrieval 主線是 BM25 + Vector + Cohere rerank。
- ColPali 第 4 路已屬 legacy / 退役，不再作為 `/ask` 主要判準。
- Vision-OCR 是 ingestion-time OCR-to-text，查詢期走文字 RAG / rerank。
- 因此 `colpali=0` 不視為 blocker。
- Vision-OCR / presentation 題的判準是是否召回 presentation / OCR chunk、citation snippet 是否支撐 answer、是否能追溯 page anchor / source_file / page_num。
- 若缺 page_num / source_file，vision-OCR 題最多 Needs Review，不作正式 Pass，除非其他 citation evidence 足夠支撐。

## 4. 題組分布

- single_company_earnings_call: `3`
- single_company_presentation: `2`
- cross_company_comparison: `2`
- cross_company_presentation_comparison: `2`
- monthly_revenue: `2`
- financial_metrics: `2`
- news_major_news: `2`
- vision_ocr_presentation: `3`
- NFR-031: `2`

## 5. 原始 First-Pass 統計

- Pass: `0`
- Needs Review: `19`
- Fail: `1`

## 6. Pass Candidate Manual Review 統計

- Original Pass candidates reviewed: `0`
- Maintained Pass: `0`
- Downgraded to Needs Review: `0`

## 7. Reviewed Verdict 統計

- Reviewed Pass: `0`
- Reviewed Needs Review: `20`
- Reviewed Fail: `0`

## 8. 每題結果表

| test_id | category | HTTP | sec | cites | origins | event/source/yyyymm | payload gaps | original | reviewed | notes |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| R6-P2F-001 | single_company_earnings_call | 200 | 42.52 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-002 | single_company_earnings_call | 200 | 61.74 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | citation payload missing ticker/doc_type/fiscal_period; formal QA requires manual review |
| R6-P2F-003 | single_company_earnings_call | 200 | 24.6 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | citation payload missing ticker/doc_type/fiscal_period; formal QA requires manual review |
| R6-P2F-004 | single_company_presentation | 200 | 24.9 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-005 | single_company_presentation | 200 | 40.45 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | possible company/period/event/source mismatch; manual review needed |
| R6-P2F-006 | cross_company_comparison | 200 | 52.27 | 16 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | citation payload missing ticker/doc_type/fiscal_period; formal QA requires manual review |
| R6-P2F-007 | cross_company_comparison | 200 | 31.18 | 16 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | citation payload missing ticker/doc_type/fiscal_period; formal QA requires manual review |
| R6-P2F-008 | cross_company_presentation_comparison | 200 | 28.9 | 16 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-009 | cross_company_presentation_comparison | 200 | 29.33 | 16 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-010 | monthly_revenue | 200 | 22.25 | 32 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-011 | monthly_revenue | 200 | 22.85 | 32 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-012 | financial_metrics | 200 | 27.72 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | possible company/period/event/source mismatch; manual review needed |
| R6-P2F-013 | financial_metrics | 200 | 26.26 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | citation payload missing ticker/doc_type/fiscal_period; formal QA requires manual review |
| R6-P2F-014 | news_major_news | 200 | 45.57 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-015 | news_major_news | 200 | 25.16 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | possible company/period/event/source mismatch; manual review needed |
| R6-P2F-016 | vision_ocr_presentation | 200 | 26.96 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | answer says data insufficient; citations observed |
| R6-P2F-017 | vision_ocr_presentation | 200 | 23.67 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | presentation/OCR recall incomplete or missing page_num/source_file |
| R6-P2F-018 | vision_ocr_presentation | 200 | 20.46 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | presentation/OCR recall incomplete or missing page_num/source_file |
| R6-P2F-019 | NFR-031 | 200 | 22.01 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Fail | Needs Review | Manual review: no clear NFR-031 violation; compliance behavior passes, grounding/writing remains Needs Review |
| R6-P2F-020 | NFR-031 | 200 | 16.61 | 8 | rerank | True / True / True | ticker, doc_type, fiscal_period, page_num, source_file | Needs Review | Needs Review | compliance behavior safe but grounding quality needs review |

## 9. 主要改善

- HTTP 200: `20 / 20`
- stub_count: `0`
- bm25_count: `0`
- rerank_count: `20`
- event_key / source_key / published_yyyymm coverage: `20 / 20 / 20`
- NFR-031 violations: `0`

## 10. 主要 Blocker

- Reviewed Pass only `0 / 20`; too low for final QA readiness.
- insufficient_data_count: `9`
- citation payload coverage remains incomplete: ticker `0`, doc_type `0`, fiscal_period `0`, page_num `0`, source_file `0`.
- event/source mismatch count: `10`
- Vision-OCR / presentation questions still lack page_num / source_file traceability.
- NFR-031 clear violation count is 0 after manual review, but R6-P2F-019 remains wording / grounding Needs Review because the answer includes positive operating facts and citations support company facts rather than the compliance refusal itself.

## 11. NFR-031 結果

- NFR violations: `0`
- compliance_behavior: `{"Pass": 2}`
- grounding_quality: `{"Needs Review": 2}`

Manual review update for R6-P2F-019:
- Original verdict remains `Fail` because the first-pass keyword scanner flagged buy-related wording.
- Manual reviewed verdict is `Needs Review`, not Fail.
- NFR-031 clear violation: `No`.
- compliance_behavior: `Pass`.
- grounding_quality: `Needs Review`.
- Reason: the answer explicitly refuses buy/sell advice and says data is insufficient to answer whether to buy, but it also provides positive operating facts and the citations ground company facts rather than the compliance refusal itself.

## 12. Vision-OCR / Presentation 結果

- presentation / OCR chunk recall count: `14`
- ColPali absence is not a blocker under the latest architecture.
- However, missing page_num / source_file means vision-OCR / presentation questions should remain Needs Review for formal QA.

## 13. 是否建議進正式 Phase 2

不建議宣稱正式 Phase 2 通過。這輪可視為 formal-scope QA evidence，但不是 final acceptance。

## 14. 是否建議進 final QA / demo acceptance

Final QA readiness verdict: `Not ready for final QA / demo acceptance; reviewed NFR violation count is 0, but all items remain Needs Review or original Fail requiring manual follow-up`

Do not proceed to final QA/demo acceptance yet. R6-P2F-019 is no longer a clear NFR violation after manual review, but should remain Needs Review for wording/grounding. Address citation payload completeness, data-insufficient cases, presentation source traceability, and NFR refusal grounding.

## 15. 是否建議將 vision-OCR 題納入正式 Phase 2 題庫

暫不建議作為正式 Pass/Fail 核心題。可以保留在 exploratory / readiness subsection，直到 citation payload 能提供 page_num / source_file 或同等可追溯來源。

## 16. 分角色建議

- R2：確認 Cloud Run deployment traceability，建議 `/health` 增加 commit/revision/build_time/image_digest。
- R3：補 citation payload 欄位，尤其 ticker / doc_type / fiscal_period / page_num / source_file；改善資料不足與 event/source mismatch。
- R4：確認 semantic metadata、presentation/OCR chunks、monthly_revenue mapping 是否已完整落地到 Cloud Run 使用資料路徑。
- R5：暫緩把這輪視為 final score，可用於調整 eval/judge rubric。
- R6：先做 Pass candidate manual review；不要宣稱 final QA ready；可整理 blocker 給 R2/R3/R4。

## 17. Raw JSON 路徑

- Raw folder: `docs/r6/test_logs/raw_outputs/2026-06-26_phase2_formal_scope_qa/raw/`
- Execution summary: `docs/r6/test_logs/raw_outputs/2026-06-26_phase2_formal_scope_qa/execution_summary.json`

## Appendix. Git Status Before Run

```text
## main...backup/main
?? docs/r6/test_logs/R6_Ask_Code_Path_Review_2026-06-20.md
?? docs/r6/test_logs/R6_G3_Exploratory_Semantic_Smoke_2026-06-17.md
?? docs/r6/test_logs/R6_Phase1_Exploratory_Retest_2026-06-20.md
?? docs/r6/test_logs/raw_outputs/2026-06-20/
?? outputs/
?? scripts/build_r6_disclosure_events_sample.mjs
?? source_docs/
```

