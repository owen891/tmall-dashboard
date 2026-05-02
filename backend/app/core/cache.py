import asyncio
import inspect
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
    """缓存装饰器 - 支持同步和异步函数"""

    def decorator(func: Callable):
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def get_cached():
                cached_result = await cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_result
                result = func(*args, **kwargs)
                await cache.set(cache_key, result, ttl)
                return result

            return loop.run_until_complete(get_cached())

        return async_wrapper if is_async else sync_wrapper

    return decorator


def invalidate_cache(pattern: str):
    """失效缓存装饰器 - 支持同步和异步函数"""

    def decorator(func: Callable):
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            await cache.delete_pattern(pattern)
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def invalidate_and_call():
                await cache.delete_pattern(pattern)
                return func(*args, **kwargs)

            return loop.run_until_complete(invalidate_and_call())

        return async_wrapper if is_async else sync_wrapper

    return decorator
