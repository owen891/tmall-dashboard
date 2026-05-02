import asyncio
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)


class TTLCache:
    """带过期时间的内存缓存"""

    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if time.time() > entry["expires"]:
                del self._cache[key]
                return None
            return entry["value"]

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            self._cache[key] = {
                "value": value,
                "expires": time.time() + (ttl or self._default_ttl),
            }

    async def delete(self, key: str) -> None:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def delete_pattern(self, pattern: str) -> None:
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]


# 全局缓存实例
cache = TTLCache(default_ttl=300)


def cached(ttl: int = 300, key_prefix: str = ""):
    """缓存装饰器"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str):
    """失效缓存装饰器"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await cache.delete_pattern(pattern)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
