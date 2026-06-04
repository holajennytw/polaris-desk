# R5 開工指南 — Ragas Eval pipeline（不等 R4，今天就能跑）

> **給誰**：R5 AI 品質 · Eval Lead（楊宗勲）。
> **為什麼是這個**：你的硬指標＝**130 題 Eval ≥ 80%（G3 過閘關鍵）**。好消息是——**系統現在就能端到端跑**（無金鑰走確定性 fallback），所以你**今天就能把 Ragas pipeline 跑通 + 起題庫**，不必等 R4 入庫。
> **誠實前提（你的 spec 已寫）**：R4 真資料前，contexts 是 stub →「**W1 分數只是 pipeline 煙測，真分從 e2e 起算**」。先把**管線與題庫**做起來，資料一到立刻有真分。

---

## 0. 系統現在就會回答（自己先試）
```bash
make setup
python -m polaris.cli ask "比較台積電與聯發科最近兩季毛利率變化"
# 會印出 Answer / Compliance / Citations / Trace —— 無金鑰也會（走確定性 fallback）
```
→ 這代表你**現在就能拿到 Ragas 需要的四件套**：`question / answer / contexts / ground_truth`。

## 1. 怎麼用程式拿到 Ragas 輸入（關鍵）
不要用 CLI 文字輸出，用 workflow 物件直接拿結構化結果：

```python
from polaris.graph.workflow import build_workflow
app = build_workflow()
r = app.invoke({"query": "台積電2025Q1毛利率？"})

r["answer"]            # 系統答案 → Ragas 的 answer
r["contexts"]          # list[dict]：{source_id, text, period} → Ragas 的 contexts（取 text）
r["citations"]         # list[Citation]：逐句引用，驗 grounding 用
r["compliance_status"] # "passed"/"blocked" → 你報告裡「買賣建議=0」的證據
```
- `contexts` 來自 [`graph/nodes/stubs.py`](../src/polaris/graph/nodes/stubs.py) 的 `_STUB_CORPUS`（每季一筆）；**R4 接真檢索後，這裡自動變真語料、你的 runner 一行不用改**。
- Deep Research 題（場景 2）另走：`from polaris.graph.deep_research.agent import run_deep_research`；回 `DeepResearchResult`（`final_answer` + `evidence`：`Citation` 清單當 contexts）。

## 2. Ragas 量什麼（對齊 SC）
| 指標 | 門檻（SC-001）| 意義 |
|---|---|---|
| Context Precision | ≥ 0.85 | 檢索到的 context 有多相關 |
| Faithfulness | ≥ 0.90 | 答案有沒有忠於 context（不幻覺）|
| Answer Relevance | ≥ 0.85 | 答案有沒有切題 |
| **達標率** | **≥ 80%**（130 題）| G3 硬門檻 |

> Ragas 本身要一個 LLM 當評審。**CI 用 1 個便宜 Flash**（省 token）；**三方 Judge（Claude+GPT+Gemini）只在 G2/G3/G4 閘門跑**（你的 spec §5）。

## 3. 最短路徑（建 `src/polaris/eval/`，目前還沒有這個套件）
```
src/polaris/eval/
  dataset.py   # 讀題庫 CSV（question, golden_answer, company, period, category, scenario）
  runner.py    # 每題 → app.invoke() → 收集 {question, answer, contexts, ground_truth}
  score.py     # 餵 Ragas，算 CP/Faithfulness/AR，回每題分 + 達標率
  report.py    # 產 Markdown/CSV 報告 + 圖表（W4 G4 用）
  __main__.py  # python -m polaris.eval  跑全題庫出分
```
依賴：`ragas` + `datasets` 設成 optional extra `[eval]`（**別進 base，CI 才不會變重**；跟 `[llmlingua]` 同手法，見 `pyproject.toml`）。Ragas 接 Gemini 當 judge 需 `langchain-google-genai`——這段最容易卡，先用小樣本（2–3 題）驗 Ragas 跑得動，再放大。

## 4. 130 題題庫怎麼長（不必憑空想）
題目從現成素材借，**對齊 4 個 Demo 場景**：
- **公司/指標**：R6 的 `Ontology_V0.7.xlsx`（在 Google Drive `Polaris Desk/04_Ontology資料字典/`，非 repo）有 50 家公司 + 財務指標字典 + 優先級A前20。
- **場景**：R1 的 `_demo場景草稿_給R1.md`（4 場景）。US1 單一公司摘要 / US2 同業比較 / US3 圖表 ColPali / US4 跨產業營收拆解（獨立 10 題）。
- **題庫格式（CSV，可 Notion 匯入）**：`題號, 場景, 問題, golden_answer, 公司, 季別, 類別, 是否紅隊`。
- **每題附 golden answer**（SC-002 驗收標準）——這是最花工的部分，可請 **R6 出財務/紅隊題 + 標 golden**（你 spec 上游就是 R6）。

> W1 先衝 **25 題**（財務/檢索基本題）把 pipeline 餵飽 → W2 75 → W3 擴到 130（含新聞/跨產業）。

## 5. 評分 CI（每次 commit 自動跑分）
- repo 已有 `.github/workflows/ci.yml`（lint+test）。你加一個 **eval job 或獨立 workflow**：跑 `python -m polaris.eval --quick`（小樣本 + 1 Flash judge），把達標率印進 job summary。
- **CI 不可跑三方 Judge / 全 130 題**（燒 token）→ 平常 commit 只跑抽樣 Flash；閘門才手動跑全量三方。

## 6. DoD（照順序勾）
- [ ] `runner.py` 能對 1 題 `app.invoke()` 收齊 Ragas 四件套
- [ ] `score.py` 用 Ragas 對 2–3 題出 CP/Faithfulness/AR（先證明跑得動）
- [ ] 題庫 CSV 起 **25 題 + golden answer**（W1）
- [ ] `python -m polaris.eval` 跑全題庫出**達標率**（W1 是煙測分、標註「stub 語料、非真分」）
- [ ] 評分 CI job 上線（1 Flash、抽樣）
- [ ] **W2 e2e（R4 資料到位）後**重跑＝第一個真分；W3 衝 ≥80%（G3）

## 7. 防雷 & 成本紀律
- **分數現在不準是正常的**（contexts 是 stub）——報告要誠實標「pipeline 煙測分 vs 真分」，別讓人誤判 G1 就過了。
- **token 紀律**：三方 Judge 只在閘門跑；embedding/answer 別為了 eval 重算；題庫一次跑完存結果，別反覆全量重跑。
- **你只出分、不修題**（spec §Out of scope）：不及格題列「不及格清單」回報 owner（R2/R3 修系統、R6 修金融事實）。
- 走 PR（main 有必過 CI + R2 review）；新依賴進 `[eval]` extra。
- 卡住找誰：workflow 呼叫 / Ragas 接 Gemini → R2（施惠棋）；題目/golden/紅隊題 → R6（黃俊維）；場景定義 → R1（郝家銘）。
