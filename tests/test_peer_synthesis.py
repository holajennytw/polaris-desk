"""Tests for _peer_synthesis (P1 — LLM-polished peer-compare summary)."""
from __future__ import annotations


import polaris.api as api_mod


class _FakeLLM:
    def __init__(self, responses: list[str], default: str = "CLEAN"):
        self._responses = list(responses)
        self._default = default
        self.calls: list[dict] = []

    def generate(self, prompt: str, *, flash: bool = False, system_instruction: str | None = None):
        self.calls.append({"prompt": prompt})
        return self._responses.pop(0) if self._responses else self._default


class _BoomLLM:
    def generate(self, *_, **__):
        raise RuntimeError("boom")


BASE = "比較期間：2025Q1；毛利率：2330 55.4%（來源 fin-2330-2025Q1-gross_margin）vs 2454 45.1%（來源 fin-2454-2025Q1-gross_margin）"
# 只用 base 既有數字（55.4 / 45.1），不引入派生數字 → 過數字接地閘門。
POLISHED_OK = "台積電毛利率 55.4%（來源：fin-2330-2025Q1-gross_margin）高於聯發科 45.1%（來源：fin-2454-2025Q1-gross_margin），主因晶圓代工規模優勢。"
POLISHED_ADVICE = "台積電表現更好（來源：fin-2330-2025Q1-gross_margin），建議買進。"


class TestPeerSynthesis:
    def test_flag_off_returns_base(self, monkeypatch):
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "0")
        text, outcome = api_mod._peer_synthesis(BASE, client=_FakeLLM([POLISHED_OK]))
        assert text == BASE
        assert outcome in (api_mod.PEER_OUTCOME_FALLBACK, api_mod.PEER_OUTCOME_NO_KEY)

    def test_no_client_returns_base_no_key(self, monkeypatch):
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "1")
        text, outcome = api_mod._peer_synthesis(BASE, client=None)
        assert text == BASE
        assert outcome == api_mod.PEER_OUTCOME_NO_KEY

    def test_llm_ok_returns_polished(self, monkeypatch):
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "1")
        text, outcome = api_mod._peer_synthesis(BASE, client=_FakeLLM([POLISHED_OK, "CLEAN"]))
        assert text == POLISHED_OK
        assert outcome == api_mod.PEER_OUTCOME_POLISHED

    def test_compliance_rejection_returns_base(self, monkeypatch):
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "1")
        # "建議買進" should trigger compliance rejection
        text, outcome = api_mod._peer_synthesis(
            BASE, client=_FakeLLM([POLISHED_ADVICE, "VIOLATION"])
        )
        assert text == BASE
        assert outcome == api_mod.PEER_OUTCOME_COMPLIANCE_REJECTED

    def test_llm_exception_returns_base(self, monkeypatch):
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "1")
        text, outcome = api_mod._peer_synthesis(BASE, client=_BoomLLM())
        assert text == BASE
        assert outcome == api_mod.PEER_OUTCOME_LLM_ERROR

    def test_gate_fail_no_source_tag_returns_base(self, monkeypatch):
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "1")
        bad = "台積電表現更好，無任何來源標記。"
        text, outcome = api_mod._peer_synthesis(BASE, client=_FakeLLM([bad, "CLEAN"]))
        assert text == BASE
        assert outcome == api_mod.PEER_OUTCOME_GATE_FAILED

    def test_hallucinated_number_gate_fails(self, monkeypatch):
        """prose 含 base 沒有的數字（幻覺）→ gate_failed（憲法 §II 數字接地）。"""
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "1")
        # base 有 55.4 / 45.1；prose 捏造 88.8
        bad = "台積電毛利率 88.8%（來源：fin-2330-2025Q1-gross_margin），遙遙領先。"
        text, outcome = api_mod._peer_synthesis(BASE, client=_FakeLLM([bad, "CLEAN"]))
        assert text == BASE
        assert outcome == api_mod.PEER_OUTCOME_GATE_FAILED

    def test_grounded_numbers_pass(self, monkeypatch):
        """prose 只用 base 既有數字 → 過閘。"""
        monkeypatch.setenv("PEER_COMPARE_LLM_SYNTHESIS", "1")
        good = "台積電毛利率 55.4%（來源：fin-2330-2025Q1-gross_margin）高於聯發科 45.1%。"
        text, outcome = api_mod._peer_synthesis(BASE, client=_FakeLLM([good, "CLEAN"]))
        assert text == good
        assert outcome == api_mod.PEER_OUTCOME_POLISHED
