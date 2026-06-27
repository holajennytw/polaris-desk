"""Tests for _llm_suggestions (P3 — LLM-generated suggestion chips, NO grounding).

P3 接地觸點：動態問句只需 NO_ADVICE_CLAUSE（問句不含事實/數字，無來源可接地）。
任一失敗（flag 關 / 無金鑰 / 例外 / 空輸出 / compliance 拒）→ 退回規則式 presets、token=0。
"""
from __future__ import annotations

import polaris.api as api_mod

PRESETS = ["規則問句一？", "規則問句二？", "規則問句三？"]
GOOD = "台積電 2025Q1 毛利率變化原因？\n聯發科最近一季營收年增率？\n鴻海營業利益率趨勢？"
ADVICE = "台積電現在可以買進嗎？\n建議加碼哪一檔？\n該減碼聯發科嗎？"


class _FakeLLM:
    def __init__(self, responses: list[str], default: str = "CLEAN"):
        self._responses = list(responses)
        self._default = default

    def generate(self, prompt: str, *, flash: bool = False, system_instruction: str | None = None):
        return self._responses.pop(0) if self._responses else self._default


class _BoomLLM:
    def generate(self, *_, **__):
        raise RuntimeError("boom")


class TestLLMSuggestions:
    def test_flag_off_returns_presets(self, monkeypatch):
        monkeypatch.setenv("SUGGESTIONS_LLM", "0")
        out, outcome = api_mod._llm_suggestions("research", PRESETS, client=_FakeLLM([GOOD]))
        assert out == PRESETS
        assert outcome == api_mod.SUGG_OUTCOME_FALLBACK

    def test_no_client_returns_presets_no_key(self, monkeypatch):
        monkeypatch.setenv("SUGGESTIONS_LLM", "1")
        out, outcome = api_mod._llm_suggestions("research", PRESETS, client=None)
        assert out == PRESETS
        assert outcome == api_mod.SUGG_OUTCOME_NO_KEY

    def test_llm_ok_returns_generated(self, monkeypatch):
        monkeypatch.setenv("SUGGESTIONS_LLM", "1")
        out, outcome = api_mod._llm_suggestions(
            "research", PRESETS, client=_FakeLLM([GOOD, "CLEAN"])
        )
        assert out == [
            "台積電 2025Q1 毛利率變化原因？",
            "聯發科最近一季營收年增率？",
            "鴻海營業利益率趨勢？",
        ]
        assert outcome == api_mod.SUGG_OUTCOME_LLM

    def test_llm_exception_returns_presets(self, monkeypatch):
        monkeypatch.setenv("SUGGESTIONS_LLM", "1")
        out, outcome = api_mod._llm_suggestions("research", PRESETS, client=_BoomLLM())
        assert out == PRESETS
        assert outcome == api_mod.SUGG_OUTCOME_LLM_ERROR

    def test_empty_output_returns_presets(self, monkeypatch):
        monkeypatch.setenv("SUGGESTIONS_LLM", "1")
        out, outcome = api_mod._llm_suggestions(
            "research", PRESETS, client=_FakeLLM(["   \n  \n"])
        )
        assert out == PRESETS
        assert outcome == api_mod.SUGG_OUTCOME_EMPTY

    def test_advice_output_rejected_returns_presets(self, monkeypatch):
        """NFR-031：生成問句含買賣字眼 → compliance 拒 → 退回 presets。"""
        monkeypatch.setenv("SUGGESTIONS_LLM", "1")
        out, outcome = api_mod._llm_suggestions(
            "research", PRESETS, client=_FakeLLM([ADVICE, "VIOLATION"])
        )
        assert out == PRESETS
        assert outcome == api_mod.SUGG_OUTCOME_COMPLIANCE_REJECTED

    def test_caps_at_five(self, monkeypatch):
        monkeypatch.setenv("SUGGESTIONS_LLM", "1")
        many = "\n".join(f"問句{i}？" for i in range(8))
        out, outcome = api_mod._llm_suggestions("peer", PRESETS, client=_FakeLLM([many, "CLEAN"]))
        assert len(out) == 5
        assert outcome == api_mod.SUGG_OUTCOME_LLM


class TestSuggestionsEndpoint:
    def test_endpoint_flag_off_is_rule_source(self, monkeypatch):
        monkeypatch.setenv("SUGGESTIONS_LLM", "0")
        resp = api_mod.suggestions(mode="research")
        assert resp.source == "rule"
        assert resp.suggestions == api_mod._SUGGESTION_PRESETS["research"]
        assert resp.is_generating is False
