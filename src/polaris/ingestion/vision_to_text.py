"""Vision 路由判斷 + 結果攤平（純函式，零外呼，好單測）。"""
from __future__ import annotations

from .vision_schema import PageExtraction

#: 頁面非空白字元少於此 → 視為掃描/圖檔頁（pypdf 抽不出文字）。
_TEXT_FLOOR = 20


def should_vision_route(page_text: str, *, doc_type: str) -> bool:
    """簡報頁一律走 vision；其餘頁文字過少（掃描頁）才走 vision。"""
    if doc_type == "presentation":
        return True
    return len("".join((page_text or "").split())) < _TEXT_FLOOR


def _fmt(value: float | None, unit: str | None) -> str:
    # 整數值的 float（pydantic 把 36 收成 36.0）去掉 .0，避免幻覺出原頁沒有的小數精度。
    num = int(value) if value is not None and float(value).is_integer() else value
    return f"{num}{unit or ''}"


def flatten_extraction(p: PageExtraction) -> str:
    """PageExtraction → 可讀且可檢索的 page text。None 值一律略過（接地、不編造）。"""
    lines: list[str] = []
    if p.page_summary:
        lines.append(p.page_summary)
    for kv in p.key_values:
        if kv.value is not None:
            lines.append(f"{kv.label}: {_fmt(kv.value, kv.unit)}")
    for chart in p.charts:
        title = chart.title or chart.chart_type
        pairs = [f"{s.label}: {_fmt(s.value, s.unit)}" for s in chart.series
                 if s.value is not None]
        if pairs:
            lines.append(f"{title}（{chart.chart_type}）: " + "、".join(pairs))
    if p.table_markdown:
        lines.append(p.table_markdown)
    return "\n".join(lines)
