"""新聞評估卡的輸入 / 輸出契約（FR-006 / R3 spec）。

- ``NewsItem``：生產者契約（R4 新聞表 / mock JSON）。``content`` 視為不可信資料（LLM01）。
- ``NewsCard`` / ``NewsContradiction``：``evaluate_news`` 的輸出，供 R7 / Demo 消費。

鏡像 ``graph/watchdog/{events,state}.py``：輸入 pydantic frozen、輸出 dataclass。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from polaris.graph.compliance import ComplianceStatus
from polaris.graph.state import Citation


class NewsItem(BaseModel):
    """一則新聞（生產者端契約）。content 視為不可信資料（LLM01）。"""

    model_config = ConfigDict(frozen=True)

    item_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    published_at: datetime
    title: str = Field(min_length=1)
    source: str = Field(default="")          # 媒體 / 出處名稱
    url: str = Field(default="")             # 出處連結（接地用）
    content: str = Field(default="")         # 不可信資料
    credibility: str | None = Field(default=None)  # R6 白名單分級（上游給；卡片只描述、不自評）


@dataclass
class NewsContradiction:
    """一組互相矛盾的新聞（標矛盾）。statements 至少 2 條、各帶來源接地。"""

    topic: str
    statements: list[Citation] = field(default_factory=list)


@dataclass
class NewsCard:
    """新聞評估卡輸出契約：只描述 / 標證據 / 標矛盾，**0 買賣建議**（NFR-031）。"""

    ticker: str
    description: str
    compliance_status: ComplianceStatus
    evidence: list[Citation] = field(default_factory=list)
    contradictions: list[NewsContradiction] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def load_mock_items(path: str | Path) -> list[NewsItem]:
    """從 JSON fixture 載入新聞清單（R4 真實新聞表之前的 mock）。"""
    raw: list[dict] = json.loads(Path(path).read_text(encoding="utf-8"))
    return [NewsItem.model_validate(item) for item in raw]


__all__ = ["NewsItem", "NewsContradiction", "NewsCard", "load_mock_items"]
