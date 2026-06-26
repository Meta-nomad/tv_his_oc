import time
from typing import Any, Optional

# In-memory cache: key -> (value, expire_at)
_cache: dict[str, tuple[Any, float]] = {}


def cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expire_at = entry
    if time.time() > expire_at:
        del _cache[key]
        return None
    return value


def cache_set(key: str, value: Any, ttl: int) -> None:
    _cache[key] = (value, time.time() + ttl)


def cache_clear() -> None:
    _cache.clear()
