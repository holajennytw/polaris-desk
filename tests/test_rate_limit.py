"""app 層限流（選項 A）—— 把「匿名經 web /api/* 代轉燒配額」的成本護欄缺口補到 100。

兩層測試：
- 純 :class:`RateLimiter`（注入假時鐘 → 視窗到期、分桶、關閉、有界記憶體都可決定式驗）。
- /ask、/research 經 FastAPI 守門：cloud 才限流、local/CI 放行（保 token-free）、XFF 分桶。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from polaris.api import _RESEARCH_LIMITER, app
from polaris.config import settings
from polaris.ratelimit import RateLimiter


class _Clock:
    """可前進的假時鐘——免 sleep 驗視窗到期。"""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class TestRateLimiter:
    def test_allows_up_to_limit(self) -> None:
        rl = RateLimiter(window_s=60, now=_Clock())
        assert all(rl.hit("k", 3) for _ in range(3))

    def test_blocks_over_limit(self) -> None:
        rl = RateLimiter(window_s=60, now=_Clock())
        for _ in range(3):
            rl.hit("k", 3)
        assert rl.hit("k", 3) is False

    def test_window_resets(self) -> None:
        clk = _Clock()
        rl = RateLimiter(window_s=60, now=clk)
        for _ in range(3):
            rl.hit("k", 3)
        assert rl.hit("k", 3) is False
        clk.advance(60.0)
        assert rl.hit("k", 3) is True

    def test_keys_independent(self) -> None:
        rl = RateLimiter(window_s=60, now=_Clock())
        for _ in range(3):
            rl.hit("a", 3)
        assert rl.hit("a", 3) is False
        assert rl.hit("b", 3) is True

    def test_zero_limit_disables(self) -> None:
        rl = RateLimiter(window_s=60, now=_Clock())
        assert all(rl.hit("k", 0) for _ in range(100))

    def test_bounded_memory_purges_expired(self) -> None:
        clk = _Clock()
        rl = RateLimiter(window_s=60, now=clk, max_keys=10)
        for i in range(10):
            rl.hit(f"k{i}", 5)
        clk.advance(120.0)  # 全部過期
        rl.hit("new", 5)  # 觸發 purge
        assert len(rl._buckets) <= 10


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter():
    _RESEARCH_LIMITER.reset()
    yield
    _RESEARCH_LIMITER.reset()


class TestRateLimitGuard:
    def test_local_not_rate_limited(self, client, monkeypatch) -> None:
        """local（預設）不限流——保 token-free 開發 / CI / demo。"""
        monkeypatch.setattr(settings, "app_env", "local")
        for _ in range(10):
            assert client.post("/ask", json={"query": "台積電營收"}).status_code == 200

    def test_cloud_ask_rate_limited(self, client, monkeypatch) -> None:
        monkeypatch.setattr(settings, "app_env", "cloud")
        monkeypatch.setattr(settings, "rate_limit_per_min", 2)
        assert client.post("/ask", json={"query": "台積電營收"}).status_code == 200
        assert client.post("/ask", json={"query": "台積電營收"}).status_code == 200
        r = client.post("/ask", json={"query": "台積電營收"})
        assert r.status_code == 429
        assert r.headers.get("Retry-After") == "60"

    def test_cloud_research_rate_limited(self, client, monkeypatch) -> None:
        monkeypatch.setattr(settings, "app_env", "cloud")
        monkeypatch.setattr(settings, "rate_limit_per_min", 1)
        assert (
            client.post("/research", json={"question": "比較台積電與聯發科毛利率"}).status_code
            == 200
        )
        assert (
            client.post("/research", json={"question": "比較台積電與聯發科毛利率"}).status_code
            == 429
        )

    def test_cloud_zero_limit_disables(self, client, monkeypatch) -> None:
        """rate_limit_per_min=0 → 即使 cloud 也關閉（escape hatch）。"""
        monkeypatch.setattr(settings, "app_env", "cloud")
        monkeypatch.setattr(settings, "rate_limit_per_min", 0)
        for _ in range(5):
            assert client.post("/ask", json={"query": "台積電營收"}).status_code == 200

    def test_cloud_xff_buckets_independent(self, client, monkeypatch) -> None:
        """不同 X-Forwarded-For 各自分桶——一個來源被擋不影響另一個。"""
        monkeypatch.setattr(settings, "app_env", "cloud")
        monkeypatch.setattr(settings, "rate_limit_per_min", 1)
        h1 = {"X-Forwarded-For": "1.1.1.1"}
        h2 = {"X-Forwarded-For": "2.2.2.2"}
        assert client.post("/ask", json={"query": "台積電營收"}, headers=h1).status_code == 200
        assert client.post("/ask", json={"query": "台積電營收"}, headers=h1).status_code == 429
        assert client.post("/ask", json={"query": "台積電營收"}, headers=h2).status_code == 200
