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


class _Quota429(Exception):
    """模擬 google-genai 配額耗盡（429 / RESOURCE_EXHAUSTED）。"""

    def __init__(self) -> None:
        super().__init__("429 RESOURCE_EXHAUSTED")
        self.code = 429


def _patch_genai_rotating(monkeypatch, *, exhausted_keys, keys):
    """Fake genai.Client where clients built with a key in ``exhausted_keys``
    raise 429 on every call; others succeed. Returns the call log [(key, op)]."""
    import google.genai as genai_mod

    from polaris.config import settings

    log: list[tuple[str, str]] = []

    class _FakeModels:
        def __init__(self, key: str) -> None:
            self.key = key

        def _maybe_429(self, op: str):
            log.append((self.key, op))
            if self.key in exhausted_keys:
                raise _Quota429()

        def generate_content(self, model, contents, config):  # noqa: ARG002
            self._maybe_429("generate")
            return type("R", (), {"text": f"gen::{self.key}", "candidates": []})()

        def embed_content(self, model, contents, config):  # noqa: ARG002
            self._maybe_429("embed")
            return type(
                "R", (), {"embeddings": [type("E", (), {"values": [0.1, 0.2, 0.3]})()]}
            )()

    def _fake_client(**kw):
        return type("C", (), {"models": _FakeModels(kw.get("api_key", "vertex"))})()

    monkeypatch.setattr(genai_mod, "Client", _fake_client)
    monkeypatch.setattr(settings, "gemini_api_key", ",".join(keys))
    monkeypatch.setattr(settings, "gemini_use_vertex", False)
    return log


class TestKeyRotation:
    def test_generate_rotates_to_second_key_on_429(self, monkeypatch):
        log = _patch_genai_rotating(monkeypatch, exhausted_keys={"k1"}, keys=["k1", "k2"])
        c = gemini.GeminiClient()
        # k1 配額耗盡 → 自動輪到 k2 成功
        assert c.generate("hi") == "gen::k2"
        assert log == [("k1", "generate"), ("k2", "generate")]

    def test_embed_rotates_to_second_key_on_429(self, monkeypatch):
        log = _patch_genai_rotating(monkeypatch, exhausted_keys={"k1"}, keys=["k1", "k2"])
        c = gemini.GeminiClient()
        assert c.embed("台積電") == [0.1, 0.2, 0.3]
        assert log == [("k1", "embed"), ("k2", "embed")]

    def test_all_keys_exhausted_raises_429(self, monkeypatch):
        import pytest

        _patch_genai_rotating(monkeypatch, exhausted_keys={"k1", "k2"}, keys=["k1", "k2"])
        c = gemini.GeminiClient()
        # 全數 429 → 拋出（由外層 call_with_retry 接手退避）
        with pytest.raises(_Quota429):
            c.generate("hi")

    def test_non_quota_error_does_not_rotate(self, monkeypatch):
        """非 429 錯誤（如 400）不輪 key——立刻拋出。"""
        import google.genai as genai_mod
        import pytest

        from polaris.config import settings

        log: list[str] = []

        class _Bad(Exception):
            def __init__(self):
                super().__init__("bad request")
                self.code = 400

        class _FakeModels:
            def __init__(self, key):
                self.key = key

            def generate_content(self, model, contents, config):  # noqa: ARG002
                log.append(self.key)
                raise _Bad()

        monkeypatch.setattr(
            genai_mod, "Client",
            lambda **kw: type("C", (), {"models": _FakeModels(kw.get("api_key"))})(),
        )
        monkeypatch.setattr(settings, "gemini_api_key", "k1,k2")
        monkeypatch.setattr(settings, "gemini_use_vertex", False)
        c = gemini.GeminiClient()
        with pytest.raises(_Bad):
            c.generate("hi")
        assert log == ["k1"]  # 不輪到 k2


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
