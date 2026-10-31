import math
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def client_ip(request: Request):
    # Behind a reverse proxy (Render, Railway, Nginx...) every request comes from the
    # proxy's IP, so the real client is in X-Forwarded-For. Only trust that header when
    # TRUST_PROXY=1, otherwise anyone could spoof it to dodge the limit.
    if os.getenv("TRUST_PROXY") == "1":
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """In-memory sliding-window limiter, usable as a FastAPI dependency."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key):
        """Record a hit for key. Returns 0 if allowed, else seconds until a slot frees up."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(self.window - (now - hits[0])))
            hits.append(now)
            return 0

    def reset(self):
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request):
        retry_after = self.check(client_ip(request))
        if retry_after:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Please try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
