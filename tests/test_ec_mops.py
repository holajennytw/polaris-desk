"""MOPS 法人說明會一覽表解析（無網路，注入 fake http_get 回存檔 fixture）。"""
from __future__ import annotations

from pathlib import Path

import ec_mops

FIXTURE = Path(__file__).parent / "fixtures" / "mops_t100sb02_2891.html"


def _fake_http_get(_url: str) -> bytes:
    return FIXTURE.read_bytes()


def test_fetch_parses_quarterly_presentations():
    docs = ec_mops.fetch("2891", [2025], _fake_http_get)
    assert docs
    periods = {d.fiscal_period for d in docs}
    assert {"2024Q4", "2025Q1", "2025Q2", "2025Q3"} <= periods
    langs = {d.lang for d in docs}
    assert langs == {"zh", "en"}
    assert all(d.doc_type == "presentation" for d in docs)
    assert all(d.source_url.startswith("https://mopsov.twse.com.tw/nas/STR/") for d in docs)
    assert all(len(d.event_date) == 10 for d in docs)
    q1_zh = [d for d in docs if d.fiscal_period == "2025Q1" and d.lang == "zh"]
    assert q1_zh and q1_zh[0].source_url.endswith("289120250516M001.pdf")


_ROW_NO_QUARTER = """
<table><tr data-type='body'>
<td>6505</td><td>台塑化</td><td>113/05/09</td><td>15:00</td><td>元富證券</td>
<td>本公司受邀參加元富證券法人座談會，說明近期營運概況</td>
<td><a href='#' onclick='...value="650520240508M001.pdf";...'>650520240508M001.pdf</a></td>
<td><a href='#' onclick='...value="650520240508E001.pdf";...'>650520240508E001.pdf</a></td>
</tr></table>
"""


def test_fetch_falls_back_to_filename_date_when_subject_has_no_quarter():
    # 台塑化等公司主旨只寫「說明近期營運概況」→ 期別改由檔名日期推（最近已結束季度）
    docs = ec_mops.fetch("6505", [2024], lambda _u: _ROW_NO_QUARTER.encode())
    assert {d.fiscal_period for d in docs} == {"2024Q1"}
    assert {d.lang for d in docs} == {"zh", "en"}
    assert all(d.event_date == "2024-05-08" for d in docs)


_ROWS_REUSED_FILE = """
<table>
<tr data-type='body'>
<td>6505</td><td>台塑化</td><td>113/07/01</td><td>15:00</td><td>某券商</td>
<td>受邀參加座談會，說明近期營運概況</td>
<td><a>650520240701M001.pdf</a></td>
</tr>
<tr data-type='body'>
<td>6505</td><td>台塑化</td><td>113/07/01</td><td>15:00</td><td>某券商</td>
<td>說明113年度第1季營運成果</td>
<td><a>650520240701M001.pdf</a></td>
</tr>
</table>
"""


def test_subject_quarter_beats_filename_date_fallback():
    # 同檔名跨列重用：主旨有明示季別（2024Q1）優先於檔名日期推估（20240701→2024Q2）
    docs = ec_mops.fetch("6505", [2024], lambda _u: _ROWS_REUSED_FILE.encode())
    assert len(docs) == 1
    assert docs[0].fiscal_period == "2024Q1"


_ROW_WESTERN_YEAR_SUBJECT = """
<table><tr data-type='body'>
<td>2330</td><td>台積電</td><td>114/04/17</td><td>14:00</td><td>—</td>
<td>本公司受邀參加2025年第一季法人說明會</td>
<td><a>233020250417M001.pdf</a></td>
<td><a>233020250417E001.pdf</a></td>
</tr></table>
"""


def test_subject_with_western_4digit_year_not_misread_as_roc():
    # 回歸：台積電等公司主旨用「西元 4 碼年」（2025年第一季）。舊正規則 \d{2,3} 會抓到
    # 「025」當民國 → 1911+25 = 1936Q1（年-89 bug）。應正確解成 2025Q1。
    docs = ec_mops.fetch("2330", [2025], lambda _u: _ROW_WESTERN_YEAR_SUBJECT.encode())
    assert {d.fiscal_period for d in docs} == {"2025Q1"}
    assert {d.lang for d in docs} == {"zh", "en"}
