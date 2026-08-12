"""
简易内存缓存 — TTL 机制。

用于 KPI/趋势等高频查询，避免重复计算。
"""
import time
from functools import wraps


class SimpleCache:
    """
    简易 TTL 缓存，不依赖 Redis。
    适合本地单用户场景。

    用法:
        cache = SimpleCache(default_ttl=300)  # 5 分钟

        @cache.cached('kpi_monthly_2026-07')
        def get_kpi(dim, period):
            ...
    """

    def __init__(self, default_ttl=300):
        self._store = {}
        self._default_ttl = default_ttl

    def get(self, key):
        """获取缓存值，过期则返回 None"""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry['expires']:
            del self._store[key]
            return None
        return entry['value']

    def set(self, key, value, ttl=None):
        """设置缓存"""
        ttl = ttl or self._default_ttl
        self._store[key] = {
            'value': value,
            'expires': time.time() + ttl,
        }

    def delete(self, key):
        """删除缓存"""
        self._store.pop(key, None)

    def clear(self):
        """清空所有缓存"""
        self._store.clear()

    def cached(self, key_func=None, ttl=None):
        """
        装饰器用法。

        @cache.cached(key_func=lambda dim, period: f'kpi_{dim}_{period}', ttl=300)
        def get_kpi(dim, period):
            ...
        """
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if key_func:
                    key = key_func(*args, **kwargs)
                else:
                    key = f'{fn.__name__}_{args}_{kwargs}'

                cached_val = self.get(key)
                if cached_val is not None:
                    return cached_val

                result = fn(*args, **kwargs)
                self.set(key, result, ttl)
                return result
            return wrapper
        return decorator


# 全局缓存实例
cache = SimpleCache(default_ttl=300)
