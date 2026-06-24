"""Vision 抽取結果的結構化模型（structured output 的 response_schema）。

value 一律可為 None：頁面上沒印出的數值就留 null，不得編造（接地 / NFR-031）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Series(BaseModel):
    label: str
    value: float | None = None
    unit: str | None = None


class Chart(BaseModel):
    chart_type: str
    title: str | None = None
    series: list[Series] = Field(default_factory=list)


class KeyValue(BaseModel):
    label: str
    value: float | None = None
    unit: str | None = None


class PageExtraction(BaseModel):
    page_summary: str = ""
    charts: list[Chart] = Field(default_factory=list)
    table_markdown: str | None = None
    key_values: list[KeyValue] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("confidence")
    @classmethod
    def _normalize_confidence(cls, v: float) -> float:
        """模型有時回 0–1 外的值（實測 flash 5.0 / pro 95.0）。>1 視為百分比除以 100，
        再 clamp 到 [0,1]——否則升 Pro 門檻與 Gate1 信心欄失真。偏「低→升 Pro」是安全方向。"""
        if v > 1:
            v = v / 100
        return max(0.0, min(1.0, v))
