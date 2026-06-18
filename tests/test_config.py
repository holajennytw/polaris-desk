"""polaris.config — env 變數對應的回歸測試。

重點守 CORS 來源：runbook / `.env.example` / Cloud Run 部署指令歷史上用
`POLARIS_CORS_ORIGINS`，而 `docs/API_使用指南.md` 用 `CORS_ORIGINS`——兩者都必須
被吃進 `settings.cors_origins`，否則設了卻被 `extra="ignore"` 默默丟掉、CORS 停在
localhost 預設而擋掉 Vercel 前端（R7-1 驗收會整批失敗）。
"""
from __future__ import annotations

import pytest

from polaris.config import Settings


class TestCorsOriginsEnv:
    @pytest.mark.parametrize(
        "env_name",
        ["POLARIS_CORS_ORIGINS", "CORS_ORIGINS"],
    )
    def test_both_env_names_populate_cors_origins(self, monkeypatch, env_name):
        monkeypatch.delenv("POLARIS_CORS_ORIGINS", raising=False)
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        monkeypatch.setenv(env_name, "https://app.example.com")
        s = Settings(_env_file=None)
        assert s.cors_origins == "https://app.example.com"

    def test_polaris_prefix_wins_when_both_set(self, monkeypatch):
        # AliasChoices 順序：POLARIS_CORS_ORIGINS 優先（部署指令用的名稱）
        monkeypatch.setenv("POLARIS_CORS_ORIGINS", "https://prod.example.com")
        monkeypatch.setenv("CORS_ORIGINS", "https://other.example.com")
        s = Settings(_env_file=None)
        assert s.cors_origins == "https://prod.example.com"

    def test_default_is_localhost_dev(self, monkeypatch):
        monkeypatch.delenv("POLARIS_CORS_ORIGINS", raising=False)
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        s = Settings(_env_file=None)
        assert s.cors_origins == "http://localhost:3000,http://localhost:8501"


class TestGoogleClientIdEnv:
    def test_reads_google_client_id(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "abc.apps.googleusercontent.com")
        s = Settings(_env_file=None)
        assert s.google_client_id == "abc.apps.googleusercontent.com"
