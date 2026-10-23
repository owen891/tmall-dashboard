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


MUTATION_GENERATION_SCOPE = 'global'


def bump_mutation_generation(connection=None):
    """库内自增 mutation generation，任何进程写入后都应调用。

    CACHE-01：独立扫描进程（scripts/run_import_scanner.py）无法触发 Web
    进程的 cache.clear()。把 generation 存进库里，Web 进程拼进缓存键，
    跨进程失效就变成一次普通读取，不需要共享缓存或事件通道。
    """
    if connection is not None:
        connection.execute(
            '''INSERT INTO mutation_generation(scope, generation, updated_at)
               VALUES (?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(scope) DO UPDATE SET
                   generation = generation + 1,
                   updated_at = CURRENT_TIMESTAMP''',
            (MUTATION_GENERATION_SCOPE,),
        )
        return
    from db import get_db
    with get_db() as conn:
        bump_mutation_generation(conn)
        conn.commit()


def read_mutation_generation():
    """读取当前 generation。读到任何错误都返回 None（调用方退回不缓存/短 TTL）。"""
    try:
        from db import get_db
        with get_db() as conn:
            row = conn.execute(
                'SELECT generation FROM mutation_generation WHERE scope = ?',
                (MUTATION_GENERATION_SCOPE,),
            ).fetchone()
        return int(row['generation']) if row else 0
    except Exception:
        # 迁移尚未跑过、库不可用等情况下不能因为缓存键取不到就打断请求。
        return None

