"""Polaris Desk 輸入端守門 —— 防止使用者亂問（進 workflow 前的第一道關）。

與 output 端的 Compliance（:mod:`polaris.graph.compliance` /
:mod:`polaris.graph.nodes.compliance_agent`）對稱：**便宜、確定性的 floor 先跑、
貴的 LLM smart 層後跑，每層各自選 fail 方向**。守的是**輸入問題**，不是輸出答案。

分層（另有 L0 每人每日配額在 API 層，見 :func:`polaris.api.enforce_daily_quota`；
L3「查無足夠來源」短路在 workflow，見 :mod:`polaris.graph.workflow`）：

- **L1 注入 floor（確定性，fail-to-BLOCK）**：substring 黑名單抓 prompt-injection /
  jailbreak（「忽略以上規則」「洩漏系統提示」「開發者模式」…）。命中即擋、回固定訊息，
  **不諮詢 LLM**（跟 Compliance floor 同精神：確定性、永不被 LLM 解除）。
- **L2 範圍 floor（確定性，正向放行）**：偵測到 canonical ticker 或投研關鍵字 → 直接
  放行、**省下 LLM 成本**。floor 不做「正向攔截」——離題判定交給 L2b。
- **L2b 範圍 smart（LLM，fail-OPEN）**：floor 沒正向放行時才問 Gemini Flash 分類
  IN_SCOPE / OFF_TOPIC。LLM 任何失敗 → **放行**（fail-open，不誤擋真問題；體驗優先，
  NFR-031 仍由 output compliance 兜底）。

為何注入 = fail-to-block、範圍 = fail-open：注入是安全風險，寧可誤擋；範圍誤擋會把
「台積電 CoWoS 進度」這種沒帶關鍵字的真問題擋掉，體驗殺手，故 LLM 掛時放行。

設計目標同 Compliance：
- 純函式優先、確定性層 100% 可單元測試。
- **零改寫**：攔截輸出恆為固定常數字串 → 無 prompt-injection surface。
- 黑名單 / 關鍵字集擴充一律走 PR + red-team（別在別處 drift）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from polaris.graph.prompts import SCOPE_SYSTEM_PROMPT
from polaris.ontology import detect_tickers
from polaris.retry import call_with_retry


class _LLM(Protocol):
    def generate(
        self, prompt: str, *, flash: bool = ..., system_instruction: str | None = ...
    ) -> str: ...


GateReason = Literal["ok", "injection", "off_topic"]


# ---------------------------------------------------------------------------
# L1 注入 floor 黑名單（高精度、低誤判；擴充走 PR + red-team）
# ---------------------------------------------------------------------------
#: prompt-injection / jailbreak 片段。**刻意保守**（誤擋真問題比漏抓更傷體驗）：
#: 只收「明確要求改變行為 / 洩漏系統提示 / 越獄」的片語，不收 "prompt"、"洩漏" 等單字。
#: 英文片段比對前一律轉小寫；中文片段大小寫無關。
INJECTION_PATTERNS: tuple[str, ...] = (
    # 中文：忽略 / 無視 / 解除規則
    "忽略以上",
    "忽略上述",
    "忽略先前",
    "忽略前面的指示",
    "忽略你的指示",
    "無視以上",
    "無視上述",
    "無視你的規則",
    "不用遵守",
    "解除你的限制",
    "解除所有限制",
    # 中文：洩漏 / 揭露系統提示
    "你的系統提示",
    "系統提示詞",
    "揭露你的指示",
    "顯示你的指示",
    "說出你的系統",
    "洩漏系統提示",
    "洩露系統提示",
    # 中文：越獄 / 開發者模式
    "開發者模式",
    "越獄模式",
    "扮演一個沒有限制",
    # 英文（比對前轉小寫）
    "ignore previous",
    "ignore all previous",
    "ignore the above",
    "ignore your instructions",
    "ignore your rules",
    "disregard previous",
    "disregard the above",
    "system prompt",
    "reveal your prompt",
    "reveal your instructions",
    "show your system prompt",
    "developer mode",
    "jailbreak",
    "act as dan",
    "you are now dan",
)


# ---------------------------------------------------------------------------
# L2 範圍 floor 正向放行關鍵字（命中即視為投研題，跳過 LLM）
# ---------------------------------------------------------------------------
#: 台股投研語彙。命中任一 → 正向放行（連同 canonical ticker 偵測）。寧可放行也不誤擋，
#: 故偏寬；真正的離題攔截靠 L2b LLM。英文以小寫比對。
_SCOPE_KEYWORDS: tuple[str, ...] = (
    # 市場
    "台股", "上市", "上櫃", "證交所", "加權指數", "大盤", "類股",
    # 財報 / 財務
    "財報", "季報", "年報", "營收", "毛利", "營益率", "營業利益",
    "淨利", "稅後", "每股盈餘", "獲利", "虧損", "營運", "財測", "財務",
    "資本支出", "現金流", "負債", "資產", "存貨", "庫存", "折舊",
    # 估值 / 股利
    "股價", "股票", "本益比", "殖利率", "配息", "股利", "股息", "市值", "市占",
    # 產業 / 營運
    "產能", "訂單", "出貨", "供應鏈", "產業", "同業", "競爭", "展望", "指引",
    "法說", "法人說明會", "法人", "外資", "投信", "董事會", "並購", "增資", "減資",
    # 英文
    "revenue", "margin", "earnings", "guidance", "eps",
    "capex", "valuation", "dividend", "market share", "gross profit",
)


# ---------------------------------------------------------------------------
# 攔截後對外輸出的固定訊息（**不可含 INJECTION_PATTERNS / 買賣建議關鍵字**）
# ---------------------------------------------------------------------------
INJECTION_MESSAGE: str = (
    "偵測到可能的指令干擾內容，已忽略。本系統僅回答台股上市櫃公司的投研事實查詢。"
)
OFF_TOPIC_MESSAGE: str = (
    "本系統專注於台股上市櫃公司的投資研究（財報、法說會、產業與同業比較等），"
    "無法回答此類問題，請改問相關的可查證問題。"
)


@dataclass(frozen=True)
class GateDecision:
    """守門結果。``allowed=False`` 時 ``message`` 為對外固定訊息，否則為空字串。"""

    allowed: bool
    reason: GateReason
    message: str


# ---------------------------------------------------------------------------
# 確定性層（純函式，無外部依賴、100% 可測）
# ---------------------------------------------------------------------------

def flags_injection(query: str) -> bool:
    """是否命中 prompt-injection / jailbreak 黑名單。中文大小寫無關、英文轉小寫比對。"""
    q = (query or "").lower()
    return any(p in q for p in INJECTION_PATTERNS)


def looks_in_scope(query: str) -> bool:
    """是否有「投研題」的正向訊號：偵測到 canonical ticker，或命中投研關鍵字。

    只做正向放行；回 ``False`` **不代表**離題（可能只是沒帶關鍵字）——是否攔截由
    :func:`screen` 交給 LLM smart 層決定。
    """
    if detect_tickers(query):
        return True
    q = (query or "").lower()
    return any(kw in q for kw in _SCOPE_KEYWORDS)


# ---------------------------------------------------------------------------
# LLM smart 層（範圍分類；只回 verdict、永不生成內容 → 零 injection surface）
# ---------------------------------------------------------------------------

def _build_scope_prompt(query: str) -> str:
    return (
        "判斷以下問題是否屬於台股投資研究範疇。\n"
        "只回一個詞：IN_SCOPE 或 OFF_TOPIC。\n\n"
        f"問題：\n{query}"
    )


def _is_off_topic(verdict: str | None) -> bool:
    """解析 LLM verdict。token-first；空 / 模糊 → ``False``（保守放行，fail-open）。"""
    stripped = (verdict or "").strip()
    if not stripped:
        return False
    upper = stripped.upper()
    if upper.startswith("IN_SCOPE") or stripped.startswith("投研") or stripped.startswith("範疇內"):
        return False
    return upper.startswith("OFF_TOPIC") or stripped.startswith("範圍外") or stripped.startswith("離題")


def classify_off_topic(query: str, client: _LLM) -> bool:
    """用 Gemini Flash 判斷 query 是否離題（範圍外）。"""
    verdict = client.generate(
        _build_scope_prompt(query), flash=True, system_instruction=SCOPE_SYSTEM_PROMPT
    )
    return _is_off_topic(verdict)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def screen(query: str, client: _LLM | None = None) -> GateDecision:
    """輸入端守門主流程。回 :class:`GateDecision`。

    順序（fail-fast）：L1 注入 floor（命中即擋、不諮詢 LLM）→ L2 範圍 floor（正向放行、
    省 LLM）→ L2b 範圍 smart（LLM 分類；失敗 fail-open）。空白 query 直接放行，交由既有
    ``_reject_blank`` / planner 的空輸入處理，不在此重複。
    """
    q = (query or "").strip()
    if not q:
        return GateDecision(True, "ok", "")
    if flags_injection(q):
        return GateDecision(False, "injection", INJECTION_MESSAGE)
    if looks_in_scope(q):
        return GateDecision(True, "ok", "")
    if client is not None:
        try:
            off_topic = call_with_retry(lambda: classify_off_topic(q, client))
        except Exception:  # noqa: BLE001 — LLM 任何失敗都 fail-open（不誤擋真問題）
            off_topic = False
        if off_topic:
            return GateDecision(False, "off_topic", OFF_TOPIC_MESSAGE)
    return GateDecision(True, "ok", "")


def screen_query(query: str) -> GateDecision:
    """API 入口用薄包裝：尊重 ``INPUT_GATE`` flag。

    - flag 關（預設）→ 一律放行（prod / CI 行為零變動，需顯式 ``INPUT_GATE=1`` 才生效）。
    - flag 開 → 跑 :func:`screen`，LLM smart 層帶入 :func:`active_llm`（無金鑰 → floor-only）。
    """
    from polaris.config import settings

    if not settings.input_gate:
        return GateDecision(True, "ok", "")
    from polaris.llm.gemini import active_llm

    return screen(query, active_llm())


__all__ = [
    "GateDecision",
    "GateReason",
    "INJECTION_PATTERNS",
    "INJECTION_MESSAGE",
    "OFF_TOPIC_MESSAGE",
    "flags_injection",
    "looks_in_scope",
    "classify_off_topic",
    "screen",
    "screen_query",
]
