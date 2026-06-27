"""極小的進程內固定視窗限流器（security review #4：匿名成本型 DoS 護欄）。

用途：擋「匿名經 polaris-web 的 /api/* 代轉打 /ask /research 燒 LLM 配額」這條
成本缺口（Phase 0 的 internal ingress 只擋直連，擋不到代轉路徑）。刻意**不引入
slowapi / redis**——對齊本專案自寫小 guard（見 :func:`polaris.api.require_producer`）、
零外部相依、CI token-free。

侷限（誠實揭露）：
- **單一進程內存**：Cloud Run 多 instance 時各自計數，全域上限 ≈ ``limit × instances``。
  配合 Cloud Run ``--max-instances`` 即得有界天花板；要嚴格全域限流需改 Redis/Firestore。
- **固定視窗**：視窗邊界可能瞬時 2× 突發；對成本護欄足夠，要平滑可改 token bucket。
"""
from __future__ import annotations

import threading
import time
from typing import Callable


class RateLimiter:
    """每 ``key`` 每視窗 ≤ ``limit`` 次。執行緒安全、有界記憶體、時鐘可注入（便於測試）。"""

    def __init__(
        self,
        window_s: float = 60.0,
        now: Callable[[], float] = time.monotonic,
        max_keys: int = 50_000,
    ) -> None:
        self._window = float(window_s)
        self._now = now
        self._max_keys = max_keys
        self._lock = threading.Lock()
        # key -> (window_start, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    def hit(self, key: str, limit: int) -> bool:
        """記一次請求；回 ``True``=放行、``False``=超限。``limit<=0`` → 永遠放行（關閉）。"""
        if limit <= 0:
            return True
        now = self._now()
        with self._lock:
            if len(self._buckets) >= self._max_keys:
                self._purge(now)
            start, count = self._buckets.get(key, (now, 0))
            if now - start >= self._window:
                start, count = now, 0  # 視窗到期 → 重置
            count += 1
            self._buckets[key] = (start, count)
            return count <= limit

    def _purge(self, now: float) -> None:
        """清掉已過期的桶——擋大量不同 key（如 IP 輪替）撐爆記憶體。"""
        expired = [k for k, (start, _) in self._buckets.items() if now - start >= self._window]
        for k in expired:
            del self._buckets[k]

    def reset(self) -> None:
        """清空所有計數（測試隔離用）。"""
        with self._lock:
            self._buckets.clear()
