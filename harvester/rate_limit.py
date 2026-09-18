from __future__ import annotations

import random
import threading
import time
from collections import defaultdict


class DomainLimiter:
    def __init__(self, rps: float = 2.0, concurrent: int = 2):
        self.min_interval = 1.0 / max(rps, 0.01)
        self.concurrent = max(1, concurrent)
        self._last: dict[str, float] = defaultdict(float)
        self._sem: dict[str, threading.BoundedSemaphore] = {}
        self._lock = threading.Lock()

    def _sema(self, domain: str) -> threading.BoundedSemaphore:
        with self._lock:
            if domain not in self._sem:
                self._sem[domain] = threading.BoundedSemaphore(self.concurrent)
            return self._sem[domain]

    def acquire(self, domain: str) -> None:
        self._sema(domain).acquire()
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last[domain])
        if wait > 0:
            time.sleep(wait)

    def release(self, domain: str) -> None:
        with self._lock:
            self._last[domain] = time.monotonic()
        self._sema(domain).release()


def backoff_seconds(attempt: int, base: float = 1.0, cap: float = 120.0) -> float:
    exp = min(cap, base * (2 ** max(0, attempt)))
    return exp * (0.5 + random.random())
