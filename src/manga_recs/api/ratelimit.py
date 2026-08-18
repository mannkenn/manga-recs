"""In-process rate limiting for the public demo.

Scope, so the limits are read correctly: this is abuse protection for a
single-container demo on a free tier, not a distributed quota system. State is
per-process and resets on restart. Two instances would enforce the limit twice
over, and the right answer at that point is a shared store or an edge rate
limit, not a bigger dict here.

A sliding-window counter rather than a token bucket: the demo's failure mode is
somebody scripting a loop against /recommendations/, and a window gives a
predictable "N per minute" that is easy to state in a 429 and easy to reason
about. Bursts are fine, sustained load is not.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    remaining: int
    retry_after: int


class SlidingWindowLimiter:
    """Fixed request budget per client over a rolling window.

    Bounded by ``max_clients``: without a cap, one host cycling source addresses
    would grow the table until the process died, which converts a rate-limit
    bypass into an availability bug. Eviction is least-recently-seen.
    """

    def __init__(self, limit: int, window_seconds: float, max_clients: int = 4096) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        self.limit = limit
        self.window = window_seconds
        self.max_clients = max_clients
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        # Middleware runs on the event loop but handlers run in a threadpool, so
        # this is reachable from more than one thread.
        self._lock = threading.Lock()

    def check(self, client: str, now: float | None = None) -> Decision:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window

        with self._lock:
            hits = self._hits.get(client)
            if hits is None:
                hits = deque()
                self._hits[client] = hits
            self._hits.move_to_end(client)

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.limit:
                retry_after = max(1, int(hits[0] + self.window - now) + 1)
                return Decision(False, 0, retry_after)

            hits.append(now)
            self._evict()
            return Decision(True, self.limit - len(hits), 0)

    def _evict(self) -> None:
        """Drop the least-recently-seen clients once over budget.

        Called with the lock held. Evicting an active client only forgives its
        history, so the worst case is a client briefly getting extra headroom -
        strictly preferable to unbounded growth.
        """
        while len(self._hits) > self.max_clients:
            self._hits.popitem(last=False)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request) -> str:
    """Identify the caller, trusting proxy headers only when told to.

    X-Forwarded-For is client-supplied and trivially spoofed, so honouring it
    unconditionally would let anyone bypass the limit with a header. Hugging
    Face Spaces does front the container with a proxy, though, and without the
    header every request there appears to come from the same internal address -
    which would rate-limit all visitors as one client. Hence the explicit
    setting: correct in both places, guessing in neither.
    """
    from manga_recs.common.settings import settings

    if settings.api.trust_forwarded_for:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            # Leftmost entry is the original client; the rest are proxy hops.
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"
