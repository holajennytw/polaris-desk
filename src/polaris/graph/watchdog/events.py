"""MOPS 事件模型與 mock 載入（specs/003 / R3 開工指南 §3）。

``MopsEvent`` 為生產者契約：R4 真實 MOPS 爬蟲之後接這份 schema 即可，
``run_watchdog`` 的 agent 邏輯完全不動（注入式 seam，同 Deep Research ``search``）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MopsDocType = Literal["重大訊息", "法說公告", "財報公告", "其他"]


class MopsEvent(BaseModel):
    """MOPS 公告事件（生產者端契約）。content 視為不可信資料（LLM01）。"""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    published_at: datetime
    doc_type: MopsDocType = "其他"
    title: str = Field(min_length=1)
    content: str = Field(default="")


def load_mock_events(path: str | Path) -> list[MopsEvent]:
    """從 JSON fixture 載入事件清單（R4 真實來源之前的 mock）。"""
    raw: list[dict] = json.loads(Path(path).read_text(encoding="utf-8"))
    return [MopsEvent.model_validate(item) for item in raw]


__all__ = ["MopsDocType", "MopsEvent", "load_mock_events"]
