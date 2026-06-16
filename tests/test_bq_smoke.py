"""D10 — BigQuery 雲端管路煙測（polaris.diagnostics.bigquery_smoke）。

驗證上雲管路（設定 / 接線 / 連線），不需 R4 入庫資料。connectivity 把 R4 尚未
實作的 health_check（NotImplementedError）歸類為 pending（非失敗）；無金鑰 → skipped。
全程可注入 store / creds → 離線確定性可測，token=0。
"""
from __future__ import annotations

from types import SimpleNamespace

from polaris import diagnostics as d


def _settings(**kw):
    base = dict(
        vector_backend="bigquery", gcp_project="polaris-desk-team", bq_dataset="polaris_core"
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _step(report, name):
    return next(s for s in report.steps if s.name == name)


class _Store:
    """注入式假 store：health_check 回 result 或拋 exc。"""

    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    def health_check(self):
        if self._exc is not None:
            raise self._exc
        return self._result


class TestConfigStep:
    def test_config_ok_reports_project(self):
        r = d.bigquery_smoke(_settings(), creds_available=False)
        cfg = _step(r, "config")
        assert cfg.status == "ok"
        assert "polaris-desk-team" in cfg.detail

    def test_config_fail_when_no_project(self):
        r = d.bigquery_smoke(_settings(gcp_project=""), creds_available=False)
        assert _step(r, "config").status == "fail"
        assert r.overall == "fail"


class TestConnectivityStep:
    def test_skipped_when_no_creds(self):
        r = d.bigquery_smoke(_settings(), store=_Store(result=True), creds_available=False)
        assert _step(r, "connectivity").status == "skipped"

    def test_pending_on_not_implemented(self):
        r = d.bigquery_smoke(
            _settings(), store=_Store(exc=NotImplementedError()), creds_available=True
        )
        assert _step(r, "connectivity").status == "pending"
        assert r.overall == "pending"

    def test_ok_when_health_check_true(self):
        r = d.bigquery_smoke(_settings(), store=_Store(result=True), creds_available=True)
        assert _step(r, "connectivity").status == "ok"
        assert r.overall == "ok"

    def test_fail_on_health_check_false(self):
        r = d.bigquery_smoke(_settings(), store=_Store(result=False), creds_available=True)
        assert _step(r, "connectivity").status == "fail"

    def test_fail_on_exception(self):
        r = d.bigquery_smoke(
            _settings(), store=_Store(exc=RuntimeError("conn refused")), creds_available=True
        )
        assert _step(r, "connectivity").status == "fail"


class TestRealBigQueryStoreImplemented:
    """health_check 已實作（2026-06-10）：真 store + 注入 client → 零改碼轉真煙測。"""

    def test_real_store_with_fake_client_is_ok(self):
        from polaris.vectorstore.bigquery_store import BigQueryStore
        from tests.test_vectorstore_impl import FakeBQClient

        store = BigQueryStore(_settings(), client=FakeBQClient())
        r = d.bigquery_smoke(_settings(), store=store, creds_available=True)
        assert _step(r, "connectivity").status == "ok"

    def test_real_store_client_error_is_fail_not_pending(self):
        from polaris.vectorstore.bigquery_store import BigQueryStore
        from tests.test_vectorstore_impl import FakeBQClient

        store = BigQueryStore(
            _settings(), client=FakeBQClient(error=ConnectionError("no route"))
        )
        r = d.bigquery_smoke(_settings(), store=store, creds_available=True)
        assert _step(r, "connectivity").status == "fail"


class TestOverallPrecedence:
    def test_fail_beats_pending(self):
        r = d.bigquery_smoke(
            _settings(gcp_project=""), store=_Store(exc=NotImplementedError()), creds_available=True
        )
        assert r.overall == "fail"

    def test_skipped_when_config_ok_and_no_creds(self):
        assert d.bigquery_smoke(_settings(), creds_available=False).overall == "skipped"


class TestCredsGateDefault:
    def test_no_env_skips(self, monkeypatch, tmp_path):
        # 同時清掉 env 與 ADC well-known（指向空 tmp）→ 確定性「無金鑰」。
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path))
        r = d.bigquery_smoke(_settings(), store=_Store(result=True))
        assert _step(r, "connectivity").status == "skipped"

    def test_env_present_triggers_check(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake.json")
        r = d.bigquery_smoke(_settings(), store=_Store(result=True))
        assert _step(r, "connectivity").status == "ok"

    def test_adc_well_known_file_triggers_check(self, monkeypatch, tmp_path):
        # 模擬 `gcloud auth application-default login`：env 未設，但 ADC 檔存在。
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path))
        (tmp_path / "application_default_credentials.json").write_text("{}")
        r = d.bigquery_smoke(_settings(), store=_Store(result=True))
        assert _step(r, "connectivity").status == "ok"


class TestBqSmokeCLI:
    """CLI 注入已知 report，確定性測「印步驟 + 退出碼映射」，不依賴本機 .env。"""

    def test_cli_prints_steps_and_exits_zero_on_skipped(self, monkeypatch, capsys):
        from polaris import cli, diagnostics

        fake = diagnostics.SmokeReport(
            steps=[
                diagnostics.SmokeStep("config", "ok", "backend=bigquery project=x dataset=y"),
                diagnostics.SmokeStep("connectivity", "skipped", "no creds"),
            ]
        )
        monkeypatch.setattr(diagnostics, "bigquery_smoke", lambda *a, **k: fake)
        rc = cli.main(["bq-smoke"])
        out = capsys.readouterr().out
        assert rc == 0  # skipped / pending 非失敗
        assert "config" in out and "connectivity" in out
        assert "overall: skipped" in out

    def test_cli_exits_one_on_fail(self, monkeypatch, capsys):
        from polaris import cli, diagnostics

        fake = diagnostics.SmokeReport(
            steps=[diagnostics.SmokeStep("config", "fail", "gcp_project 未設定")]
        )
        monkeypatch.setattr(diagnostics, "bigquery_smoke", lambda *a, **k: fake)
        assert cli.main(["bq-smoke"]) == 1
