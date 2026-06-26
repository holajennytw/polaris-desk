"""題庫載入（R5 spec / SC-002）。

CSV 欄位（中文欄頭，對齊 R5 開工指南 §4、可 Notion 匯入）：
``題號, 場景, 問題, golden_answer, 公司, 季別, 類別, 是否紅隊``（+ 選用 ``gate_subset``）

- 場景：1=單一公司摘要（走 5 節點 workflow）、2=同業比較（走 Deep Research）、
  3=圖表 ColPali（W3 後）、4=跨產業營收拆解、5=peer-compare 接地觸點（走 `/peer-compare`）。
- 是否紅隊：``Y`` = 誘導買賣建議題，驗收標準是最終 answer 0 關鍵字（NFR-031），
  而非答案正確性。
- ``gate_subset``（R5 v1 新增、選用欄）：閘門子集標籤，如 ``scenario4_gate``
  （R5 跨產業 G4 門）/ ``prose_faithfulness``（本案 P0 敘事接地題）；v0 題庫無此欄。

預設題庫＝R5 canonical ``questions_v1.csv``（BOM + 全引號）；以 ``utf-8-sig`` 開檔。
"""
from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

#: CSV 必要欄頭 → 內部欄位名。
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

#: 選用欄頭（R5 v1 題庫新增；v0 缺此欄仍可載入）。
_OPTIONAL_COLUMNS = {
    "gate_subset": "gate_subset",
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
    #: R5 v1 閘門子集標籤（如 ``scenario4_gate`` / ``prose_faithfulness``）；v0 無此欄則空。
    gate_subset: str = Field(default="")


def load_dataset(path: str | Path) -> list[EvalItem]:
    """讀題庫 CSV → ``list[EvalItem]``；缺必要欄頭即拋（題庫格式是契約）。

    以 ``utf-8-sig`` 開檔吞掉 R5 v1 題庫的 BOM（否則首欄頭變 ``﻿題號`` → 誤判缺欄）。
    ``gate_subset`` 為選用欄，v0 題庫無此欄仍可載入。
    """
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        missing = set(_COLUMNS) - fields
        if missing:
            raise ValueError(f"題庫缺欄位：{sorted(missing)}")
        present_optional = {k: v for k, v in _OPTIONAL_COLUMNS.items() if k in fields}
        items = []
        for row in reader:
            data = {dst: (row.get(src) or "").strip() for src, dst in _COLUMNS.items()}
            for src, dst in present_optional.items():
                data[dst] = (row.get(src) or "").strip()
            data["redteam"] = data["redteam"].upper() in ("Y", "YES", "TRUE", "1")
            items.append(EvalItem(**data))
    if not items:
        raise ValueError(f"題庫為空：{path}")
    return items


__all__ = ["EvalItem", "load_dataset"]
