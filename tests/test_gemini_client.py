"""D5 — Gemini 金鑰有效性判斷（修 truthy-placeholder latent bug）。

`.env` 的佔位字串是 `'# 必填…'`：truthy 但無效。`is_real_key` 必須把
空字串 / 純空白 / `#` 開頭一律視為「未設定」，避免下游以為有金鑰卻在
呼叫時才爆。
"""
from __future__ import annotations

from polaris.llm import gemini


class TestIsRealKey:
    def test_empty_string_is_not_real(self):
        assert gemini.is_real_key("") is False

    def test_none_is_not_real(self):
        assert gemini.is_real_key(None) is False

    def test_whitespace_only_is_not_real(self):
        assert gemini.is_real_key("   ") is False

    def test_hash_placeholder_is_not_real(self):
        # 正是 .env 目前的值形態
        assert gemini.is_real_key("# 必填（主力模型 Gemini 3.0 Pro/Flash）") is False

    def test_leading_whitespace_then_hash_is_not_real(self):
        assert gemini.is_real_key("   # still a comment") is False

    def test_realistic_key_is_real(self):
        assert gemini.is_real_key("AIzaSyD-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") is True


class TestAvailable:
    def test_available_false_for_placeholder(self, monkeypatch):
        from polaris.config import settings

        monkeypatch.setattr(settings, "gemini_api_key", "# placeholder")
        assert gemini.available() is False

    def test_available_true_for_real_key(self, monkeypatch):
        from polaris.config import settings

        monkeypatch.setattr(settings, "gemini_api_key", "AIzaSyReal123")
        assert gemini.available() is True


class TestActiveLLM:
    def test_active_llm_is_none_without_real_key(self, monkeypatch):
        from polaris.config import settings

        monkeypatch.setattr(settings, "gemini_api_key", "# placeholder")
        assert gemini.active_llm() is None


def _patch_genai(monkeypatch, *, use_vertex, key="AIzaSyReal123"):
    """Patch google.genai.Client with a fake that records init kwargs and routes
    generate/embed by client tag ('vertex' vs 'apikey'). Returns (inits, log)."""
    import google.genai as genai_mod

    from polaris.config import settings

    inits: list[dict] = []
    log: list[tuple[str, str]] = []

    class _FakeModels:
        def __init__(self, tag: str) -> None:
            self.tag = tag

        def generate_content(self, model, contents, config):  # noqa: ARG002
            log.append((self.tag, "generate"))
            return type("R", (), {"text": f"gen::{self.tag}", "candidates": []})()

        def embed_content(self, model, contents, config):  # noqa: ARG002
            log.append((self.tag, "embed"))
            return type("R", (), {"embeddings": [type("E", (), {"values": [0.1, 0.2, 0.3]})()]})()

    def _fake_client(**kw):
        inits.append(kw)
        tag = "vertex" if kw.get("vertexai") else "apikey"
        return type("C", (), {"models": _FakeModels(tag)})()

    monkeypatch.setattr(genai_mod, "Client", _fake_client)
    monkeypatch.setattr(settings, "gemini_api_key", key)
    monkeypatch.setattr(settings, "gemini_use_vertex", use_vertex)
    monkeypatch.setattr(settings, "vertex_location", "global")
    monkeypatch.setattr(settings, "gcp_project", "polaris-desk-team")
    return inits, log


class TestVertexGeneration:
    def test_vertex_mode_routes_generation_to_vertex_embeddings_to_apikey(self, monkeypatch):
        inits, log = _patch_genai(monkeypatch, use_vertex=True)
        c = gemini.GeminiClient()
        # a Vertex client (project+location, ADC auth) AND an api_key client are built
        assert any(
            k.get("vertexai") and k.get("project") == "polaris-desk-team"
            and k.get("location") == "global"
            for k in inits
        )
        assert any("api_key" in k for k in inits)
        # generation → Vertex (draws on GCP project quota / trial credit)
        assert c.generate("hi", flash=True) == "gen::vertex"
        # embeddings → api_key (preserves polaris_core 768-dim vector space)
        c.embed("台積電")
        assert ("apikey", "embed") in log
        assert ("vertex", "embed") not in log

    def test_default_mode_uses_apikey_for_everything(self, monkeypatch):
        inits, log = _patch_genai(monkeypatch, use_vertex=False)
        c = gemini.GeminiClient()
        assert not any(k.get("vertexai") for k in inits)  # no Vertex client
        assert c.generate("hi", flash=True) == "gen::apikey"
        c.embed("台積電")
        assert ("apikey", "embed") in log

    def test_requires_apikey_even_in_vertex_mode(self, monkeypatch):
        """Embeddings always go through the api_key model (vector-space parity), so a
        real key is still required even when generation runs on Vertex."""
        import pytest

        from polaris.config import settings

        monkeypatch.setattr(settings, "gemini_use_vertex", True)
        monkeypatch.setattr(settings, "gemini_api_key", "# placeholder")
        with pytest.raises(RuntimeError):
            gemini.GeminiClient()
