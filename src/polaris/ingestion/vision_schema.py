"""Vision 抽取結果的結構化模型（structured output 的 response_schema）。

value 一律可為 None：頁面上沒印出的數值就留 null，不得編造（接地 / NFR-031）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


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
