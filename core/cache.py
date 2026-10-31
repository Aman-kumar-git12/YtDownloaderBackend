import threading
import time


class TTLCache:
    """Tiny thread-safe cache so repeated insight lookups don't hit YouTube again."""

    def __init__(self, ttl_seconds, max_entries=100):
        self.ttl = ttl_seconds
        self.max = max_entries
        self._data = {}
        self._lock = threading.Lock()

    def get_or_compute(self, key, compute):
        with self._lock:
            entry = self._data.get(key)
            if entry and time.time() - entry[0] < self.ttl:
                return entry[1]
        value = compute()
        with self._lock:
            if len(self._data) >= self.max:
                del self._data[min(self._data, key=lambda k: self._data[k][0])]
            self._data[key] = (time.time(), value)
        return value
