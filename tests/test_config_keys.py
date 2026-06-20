"""金鑰多值解析（429 輪替用）。

``GEMINI_API_KEY`` / ``COHERE_API_KEY`` 支援逗號分隔多把金鑰；解析時去空白、
丟掉空字串與 ``#`` 開頭佔位。單把金鑰（無逗號）= 1 元素 list，向後相容。
"""
from __future__ import annotations

from polaris.config import settings


class TestGeminiApiKeys:
    def test_single_key(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "AIzaOnly")
        assert settings.gemini_api_keys == ["AIzaOnly"]

    def test_comma_separated(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "AIzaFirst,AIzaSecond")
        assert settings.gemini_api_keys == ["AIzaFirst", "AIzaSecond"]

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", " AIzaFirst , AIzaSecond ")
        assert settings.gemini_api_keys == ["AIzaFirst", "AIzaSecond"]

    def test_drops_placeholder_and_blanks(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "AIzaReal,,# 必填,AIzaTwo")
        assert settings.gemini_api_keys == ["AIzaReal", "AIzaTwo"]

    def test_placeholder_only_is_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "# placeholder")
        assert settings.gemini_api_keys == []


class TestCohereApiKeys:
    def test_comma_separated(self, monkeypatch):
        monkeypatch.setattr(settings, "cohere_api_key", "co_first,co_second")
        assert settings.cohere_api_keys == ["co_first", "co_second"]

    def test_empty_is_empty_list(self, monkeypatch):
        monkeypatch.setattr(settings, "cohere_api_key", "")
        assert settings.cohere_api_keys == []
