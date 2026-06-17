"""評測報告（Markdown；W4 G4 用圖表另補）。"""
from __future__ import annotations

from polaris.eval.runner import EvalRecord
from polaris.eval.score import RAGAS_THRESHOLDS, SmokeReport


def render_markdown(
    records: list[EvalRecord],
    report: SmokeReport,
    *,
    is_stub_corpus: bool = True,
    ragas_scores: dict[str, float] | None = None,
) -> str:
    """產 Markdown 報告（誠實原則）。

    ``is_stub_corpus=True``（CI / 無金鑰）：contexts 為 stub 語料 → 純 pipeline 煙測。
    ``is_stub_corpus=False``（真檢索：polaris_core）：達標率即 G3/G4 煙測門檻，但煙測分
    **不**等於事實正確率——後者要 Ragas 才是完整真分。
    """
    lines = ["# Polaris Desk Eval 報告", ""]
    if is_stub_corpus:
        lines += [
            "> ⚠️ **pipeline 煙測分**（contexts 為 stub 語料）——證明管線通、合規守住；",
            "> **非 G3 真分**。R4 真資料入庫後重跑才是第一個真分。",
            "",
        ]
    else:
        lines += [
            "> ℹ️ **真資料煙測分**（contexts 來自 polaris_core 真語料）——證明管線通、引用接地、"
            "合規守住；達標率即 G3/G4 煙測門檻（≥ 80%）。",
            "> 注意：煙測分**不**等於事實正確率；完整 G3 真分需 Ragas "
            "CP/Faithfulness/AR（裝 `[eval]` extra + 金鑰）。",
            "",
        ]
    lines += [
        f"- 題數：{len(report.scores)}",
        f"- 達標率：**{report.pass_rate:.1%}**（G3 門檻 ≥ 80%）",
        f"- 紅隊題：{sum(1 for r in records if r.item.redteam)} 題、"
        f"買賣建議出現 {sum(1 for s in report.scores if not s.checks.get('no_buysell', True))} 次"
        "（目標 = 0）",
        "",
    ]
    if report.failed_ids:
        lines += ["## 不及格清單（回報 owner，R5 不修題）", ""]
        by_id = {s.item_id: s for s in report.scores}
        for item_id in report.failed_ids:
            failed = [k for k, v in by_id[item_id].checks.items() if not v]
            lines.append(f"- {item_id}：fail {', '.join(failed)}")
        lines.append("")

    if ragas_scores is not None:
        lines += ["## Ragas 真分（G3 閘門）", ""]
        all_pass = True
        for metric, score in ragas_scores.items():
            threshold = RAGAS_THRESHOLDS.get(metric, 0.0)
            ok = score >= threshold
            if not ok:
                all_pass = False
            status = "✅" if ok else "❌"
            lines.append(
                f"- **{metric}**：{score:.3f}　（門檻 {threshold}）　{status}"
            )
        lines += [
            "",
            f"> G3 {'**PASS**' if all_pass else '**FAIL** — 未達門檻，回報 R5 補強語料'}",
            "",
        ]

    return "\n".join(lines)


__all__ = ["render_markdown"]
