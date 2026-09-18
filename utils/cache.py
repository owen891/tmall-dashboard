import threading
import time


class TTLCache:
    def __init__(self, max_entries=2048):
        self._values = {}
        self._max_entries = max_entries
        self._lock = threading.RLock()

    def get(self, key):
        now = time.monotonic()
        with self._lock:
            item = self._values.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            return value

    def set(self, key, value, ttl=300):
        now = time.monotonic()
        with self._lock:
            expired = [cache_key for cache_key, (expires_at, _) in self._values.items() if expires_at <= now]
            for cache_key in expired:
                self._values.pop(cache_key, None)
            if key not in self._values and len(self._values) >= self._max_entries:
                oldest = min(self._values, key=lambda cache_key: self._values[cache_key][0])
                self._values.pop(oldest, None)
            self._values[key] = (now + ttl, value)

    def clear(self):
        with self._lock:
            self._values.clear()


cache = TTLCache()

