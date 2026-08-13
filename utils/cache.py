import time


class TTLCache:
    def __init__(self):
        self._values = {}

    def get(self, key):
        item = self._values.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= time.monotonic():
            self._values.pop(key, None)
            return None
        return value

    def set(self, key, value, ttl=300):
        self._values[key] = (time.monotonic() + ttl, value)


cache = TTLCache()
