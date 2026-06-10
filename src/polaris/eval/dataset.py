"""題庫載入（R5 spec / SC-002）。

CSV 欄位（中文欄頭，對齊 R5 開工指南 §4、可 Notion 匯入）：
``題號, 場景, 問題, golden_answer, 公司, 季別, 類別, 是否紅隊``

- 場景：1=單一公司摘要（走 5 節點 workflow）、2=同業比較（走 Deep Research）、
  3=圖表 ColPali（W3 後）、4=跨產業營收拆解。
- 是否紅隊：``Y`` = 誘導買賣建議題，驗收標準是最終 answer 0 關鍵字（NFR-031），
  而非答案正確性。
"""
from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

#: CSV 欄頭 → 內部欄位名。
_COLUMNS = {
    "題號": "item_id",
    "場景": "scenario",
    "問題": "question",
    "golden_answer": "golden_answer",
    "公司": "company",
    "季別": "period",
    "類別": "category",
    "是否紅隊": "redteam",
}


class EvalItem(BaseModel):
    """單一評測題。"""

    model_config = ConfigDict(frozen=True)

    item_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    question: str = Field(min_length=1)
    golden_answer: str = Field(default="")
    company: str = Field(default="")
    period: str = Field(default="")
    category: str = Field(default="")
    redteam: bool = Field(default=False)


def load_dataset(path: str | Path) -> list[EvalItem]:
    """讀題庫 CSV → ``list[EvalItem]``；缺欄頭即拋（題庫格式是契約）。"""
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = set(_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"題庫缺欄位：{sorted(missing)}")
        items = []
        for row in reader:
            data = {dst: (row.get(src) or "").strip() for src, dst in _COLUMNS.items()}
            data["redteam"] = data["redteam"].upper() in ("Y", "YES", "TRUE", "1")
            items.append(EvalItem(**data))
    if not items:
        raise ValueError(f"題庫為空：{path}")
    return items


__all__ = ["EvalItem", "load_dataset"]
