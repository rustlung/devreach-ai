from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    window_seconds: int
    retry_after_seconds: int | None = None


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if limit <= 0:
            raise ValueError("Количество запросов rate limit должно быть больше нуля")
        if window_seconds <= 0:
            raise ValueError("Окно rate limit должно быть больше нуля")
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock or time.time
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    def check(self, client_key: str) -> RateLimitDecision:
        now = self._clock()
        with self._lock:
            self._cleanup_all(now)
            hits = self._hits[client_key]
            self._cleanup_client(hits, now)

            if len(hits) >= self.limit:
                retry_after = max(1, int((hits[0] + self.window_seconds) - now + 0.999))
                return RateLimitDecision(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    window_seconds=self.window_seconds,
                    retry_after_seconds=retry_after,
                )

            hits.append(now)
            remaining = max(0, self.limit - len(hits))
            return RateLimitDecision(
                allowed=True,
                limit=self.limit,
                remaining=remaining,
                window_seconds=self.window_seconds,
            )

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def stored_client_count(self) -> int:
        with self._lock:
            return len(self._hits)

    def _cleanup_all(self, now: float) -> None:
        stale_keys = []
        for client_key, hits in self._hits.items():
            self._cleanup_client(hits, now)
            if not hits:
                stale_keys.append(client_key)
        for client_key in stale_keys:
            del self._hits[client_key]

    def _cleanup_client(self, hits: deque[float], now: float) -> None:
        threshold = now - self.window_seconds
        while hits and hits[0] <= threshold:
            hits.popleft()
