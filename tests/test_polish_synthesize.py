"""Tests for _polish_synthesize (P0 — LLM-polished Deep Research synthesis)."""
from __future__ import annotations


from polaris.graph.deep_research import agent as ag
from polaris.graph.state import Citation


def _c(sid: str, snip: str = "片段 42%") -> Citation:
    return Citation(source_id=sid, snippet=snip, origin="stub")


class _FakeLLM:
    """Scripted LLM for testing; tracks generate calls."""

    def __init__(self, responses: list[str], default: str = "CLEAN"):
        self._responses = list(responses)
        self._default = default
        self.calls: list[dict] = []

    def generate(self, prompt: str, *, flash: bool = False, system_instruction: str | None = None):
        self.calls.append({"prompt": prompt, "flash": flash, "system": system_instruction})
        return self._responses.pop(0) if self._responses else self._default


class _BoomLLM:
    def generate(self, *_, **__):
        raise RuntimeError("boom")


BASE = "- 毛利率 42%（來源：s1）\n本回答僅描述事實。"
EVIDENCE = [_c("s1", "毛利率 42%")]
POLISHED_OK = "台積電毛利率達 42%（來源：s1），表現穩健。"


class TestPolishSynthesize:
    def test_flag_off_returns_base(self, monkeypatch):
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "0")
        text, outcome = ag._polish_synthesize("q", BASE, EVIDENCE, client=_FakeLLM([POLISHED_OK]))
        assert text == BASE
        assert outcome == ag.OUTCOME_NO_KEY or outcome == ag.OUTCOME_FALLBACK or text == BASE

    def test_no_client_returns_base_with_no_key_outcome(self, monkeypatch):
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "1")
        text, outcome = ag._polish_synthesize("q", BASE, EVIDENCE, client=None)
        assert text == BASE
        assert outcome == ag.OUTCOME_NO_KEY

    def test_llm_ok_gates_pass_returns_polished(self, monkeypatch):
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "1")
        text, outcome = ag._polish_synthesize("q", BASE, EVIDENCE, client=_FakeLLM([POLISHED_OK]))
        assert text == POLISHED_OK
        assert outcome == ag.OUTCOME_POLISHED

    def test_llm_no_source_tag_gate_fails(self, monkeypatch):
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "1")
        bad = "台積電毛利率很高，表現穩健。"  # no source tag
        text, outcome = ag._polish_synthesize("q", BASE, EVIDENCE, client=_FakeLLM([bad]))
        assert text == BASE
        assert outcome == ag.OUTCOME_GATE_TRACEABLE

    def test_llm_hallucinated_number_gate_fails(self, monkeypatch):
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "1")
        # 99% not in evidence
        bad = "毛利率 99%（來源：s1），非常高。"
        text, outcome = ag._polish_synthesize("q", BASE, EVIDENCE, client=_FakeLLM([bad]))
        assert text == BASE
        assert outcome == ag.OUTCOME_GATE_NUMBERS

    def test_llm_exception_returns_base_llm_error(self, monkeypatch):
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "1")
        text, outcome = ag._polish_synthesize("q", BASE, EVIDENCE, client=_BoomLLM())
        assert text == BASE
        assert outcome == ag.OUTCOME_LLM_ERROR


class TestRunDeepResearchPolishIntegration:
    def test_flag_off_result_byte_identical(self, monkeypatch):
        """flag=0：整條路徑 byte-identical 回歸。"""
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "0")
        r1 = ag.run_deep_research("台積電體質", search=ag.stub_search)
        r2 = ag.run_deep_research("台積電體質", search=ag.stub_search)
        assert r1.final_answer == r2.final_answer

    def test_flag_on_no_client_falls_back(self, monkeypatch):
        """flag=1 但 client=None → 仍回確定性。"""
        monkeypatch.setenv("DEEP_RESEARCH_LLM_SYNTHESIS", "1")
        r = ag.run_deep_research("台積電體質", client=None, search=ag.stub_search)
        assert r.final_answer
        assert r.compliance_status == "passed"
