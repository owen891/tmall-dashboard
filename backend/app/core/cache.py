import asyncio
import hashlib
import inspect
import json
import time
import threading
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)


class TTLCache:
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.Lock()

    def _generate_key(self, prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
        try:
            key_data = json.dumps({"args": str(args), "kwargs": str(kwargs)}, sort_keys=True)
            key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
            return f"{prefix}:{func_name}:{key_hash}"
        except Exception:
            return f"{prefix}:{func_name}:{hash(str(args))}"

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if time.time() > entry["expires"]:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = {
                "value": value,
                "expires": time.time() + (ttl or self._default_ttl),
                "created": time.time(),
            }
            self._cache.move_to_end(key)

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def delete_pattern(self, pattern: str) -> None:
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]

    def clean_expired(self) -> int:
        with self._lock:
            now = time.time()
            keys_to_delete = [k for k, v in self._cache.items() if now > v["expires"]]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    @property
    def size(self) -> int:
        return len(self._cache)


cache = TTLCache(default_ttl=300, max_size=1000)


def cached(ttl: int = 300, key_prefix: str = ""):
    def decorator(func: Callable):
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = cache._generate_key(key_prefix, func.__name__, args, kwargs)
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = cache._generate_key(key_prefix, func.__name__, args, kwargs)
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return async_wrapper if is_async else sync_wrapper

    return decorator


def invalidate_cache(pattern: str):
    def decorator(func: Callable):
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache.delete_pattern(pattern)
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache.delete_pattern(pattern)
            return func(*args, **kwargs)

        return async_wrapper if is_async else sync_wrapper

    return decorator
