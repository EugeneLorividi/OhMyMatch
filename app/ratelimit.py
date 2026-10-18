"""In-memory rolling-window rate limiter. Subjects (IPs, handles, user ids) are kept only as
keyed hashes, never written to disk, and forgotten when their window ends or on restart."""

import hashlib
import hmac
import math
import threading
import time
from collections import deque
from collections.abc import Callable

from app.config import Rule, settings

_PRUNE_EVERY = 1000


class RateLimiter:
    def __init__(self, secret: bytes, clock: Callable[[], float] = time.monotonic) -> None:
        self._secret = secret
        self._clock = clock
        self._hits: dict[bytes, deque[float]] = {}
        self._windows: dict[bytes, int] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def _key(self, rule: Rule, subject: str) -> bytes:
        message = f"{rule.name}:{subject}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).digest()[:16]

    def _current(self, key: bytes, window: int, now: float) -> deque[float]:
        hits = self._hits.get(key)
        if hits is None:
            hits = self._hits[key] = deque()
            self._windows[key] = window
        while hits and hits[0] <= now - window:
            hits.popleft()
        return hits

    def _prune(self, now: float) -> None:
        for key in list(self._hits):
            hits = self._hits[key]
            while hits and hits[0] <= now - self._windows[key]:
                hits.popleft()
            if not hits:
                del self._hits[key], self._windows[key]

    def retry_after(self, rule: Rule, subject: str) -> int | None:
        """Seconds until one more hit is allowed, or None if it is allowed now."""
        now = self._clock()
        with self._lock:
            hits = self._current(self._key(rule, subject), rule.window_seconds, now)
            if len(hits) < rule.limit:
                return None
            return max(1, math.ceil(hits[0] + rule.window_seconds - now))

    def record(self, rule: Rule, subject: str) -> None:
        now = self._clock()
        with self._lock:
            self._current(self._key(rule, subject), rule.window_seconds, now).append(now)
            self._calls += 1
            if self._calls % _PRUNE_EVERY == 0:
                self._prune(now)

    def hit(self, rule: Rule, subject: str) -> int | None:
        """Checks and records in one step. Returns retry-after seconds when over the limit."""
        wait = self.retry_after(rule, subject)
        if wait is None:
            self.record(rule, subject)
        return wait

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._windows.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._hits)


limiter = RateLimiter(settings.secret_key.encode())
