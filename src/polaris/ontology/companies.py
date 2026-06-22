"""ticker → 公司中文 canonical 名（20 列 canonical，與 seed CSV 同步）。

⚠️ 改名／增刪 ticker 一律先改 ``docs/r6/ontology/seeds/company_dim.csv``
（與 ``polaris_core.company_dim`` 走 SOP §7），再同步這份；
``tests/test_company_names.py`` 會比對兩者，漂移即失敗。
"""
from __future__ import annotations

#: ticker → canonical 中文名（取自 seed company_dim.csv 的 company_name 欄）。
_COMPANY_NAMES: dict[str, str] = {
    "1216": "統一",
    "2303": "聯電",
    "2308": "台達電",
    "2317": "鴻海",
    "2330": "台積電",
    "2357": "華碩",
    "2382": "廣達",
    "2412": "中華電",
    "2454": "聯發科",
    "2881": "富邦金",
    "2882": "國泰金",
    "2884": "玉山金",
    "2886": "兆豐金",
    "2891": "中信金",
    "2892": "第一金",
    "3034": "聯詠",
    "3037": "欣興",
    "3231": "緯創",
    "3711": "日月光投控",
    "6669": "緯穎",
}


def company_name(ticker: str | None) -> str | None:
    """ticker → canonical 中文名；未知 ticker（或 None）回 ``None``。"""
    if not ticker:
        return None
    return _COMPANY_NAMES.get(str(ticker).strip())


def company_label(ticker: str | None) -> str:
    """引用顯示標籤：有名 → ``「台積電（2330）」``；未知 → 原 ticker（或空字串）。"""
    t = "" if ticker is None else str(ticker).strip()
    name = company_name(t)
    return f"{name}（{t}）" if name else t


def detect_tickers(text: str) -> list[str]:
    """從查詢文字偵測提及的公司 ticker（依 canonical 中文名或 4 碼代號）。

    供檢索做公司過濾用（修 cross-company citation 混淆）：
    - 問單一公司 → 回該 ticker；比較題（多家）→ 依出現順序回多個。
    - 沒偵測到任何已知公司 → 回 ``[]``（呼叫端據此不加公司過濾，維持原行為）。
    """
    if not text:
        return []
    found: list[str] = []
    for ticker, name in _COMPANY_NAMES.items():
        if (name and name in text) or (ticker in text):
            if ticker not in found:
                found.append(ticker)
    return found
