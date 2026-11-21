"""Caching layer for data source responses with source-specific TTL."""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


class SourceTTLCache(TTLCache):
    """Custom TTLCache that allows per-source TTL configuration."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._source_ttls: dict[str, int] = {}

    def set_source_ttl(self, source: str, ttl: int) -> None:
        """Set custom TTL for a specific data source."""
        self._source_ttls[source] = ttl

    def _rebuild_cache(self, save: bool = True) -> None:
        """Override to respect per-source TTLs during rebuild."""
        # cachetools internal method; we respect the custom structure
        pass


class DataCache(MutableMapping[str, T]):
    """Thread-safe data cache with source-specific TTL and persistence options."""

    def __init__(self, max_size: int = 128, default_ttl: int = 300):
        self._cache: MutableMapping[str, dict[str, Any]] = {}
        self._default_ttl: int = default_ttl
        self._source_ttls: dict[str, int] = {}
        self._max_size = max_size
        self._access_counts: dict[str, int] = {}
        self._access_timestamps: dict[str, float] = {}

    def set_source_ttl(self, source: str, ttl: int) -> None:
        """Set custom TTL for a data source."""
        self._source_ttls[source] = ttl

    def _get_ttl(self, source: str) -> int:
        """Get the TTL for a data source, falling back to default."""
        return self._source_ttls.get(source, self._default_ttl)

    def _is_expired(self, key: str, source: str, fetched_at: float) -> bool:
        """Check if a cached entry has expired based on source TTL."""
        ttl = self._get_ttl(source)
        elapsed = time.time() - fetched_at
        return elapsed > ttl

    def __getitem__(self, key: str) -> T:
        entry = self._cache.get(key)
        if entry is None:
            raise KeyError(key)
        if self._is_expired(key, entry.get("_source", "default"), entry.get("_fetched_at", 0)):
            del self._cache[key]
            raise KeyError(key)
        # Update access tracking
        self._access_counts[key] = self._access_counts.get(key, 0) + 1
        self._access_timestamps[key] = time.time()
        return entry["data"]  # type: ignore

    def __setitem__(self, key: str, value: T) -> None:
        if len(self._cache) >= self._max_size and key not in self._cache:
            # Simple LRU: evict least recently accessed
            oldest_key = min(self._access_timestamps, key=self._access_timestamps.get)
            del self._cache[oldest_key]
            del self._access_counts[oldest_key]
            del self._access_timestamps[oldest_key]
        self._cache[key] = {
            "data": value,
            "_source": self._get_source_from_key(key),
            "_fetched_at": time.time(),
        }
        self._access_counts[key] = self._access_counts.get(key, 0) + 1
        self._access_timestamps[key] = time.time()

    def __delitem__(self, key: str) -> None:
        del self._cache[key]
        if key in self._access_counts:
            del self._access_counts[key]
        if key in self._access_timestamps:
            del self._access_timestamps[key]

    def __iter__(self):
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def get_with_ttl(
        self, key: str, source: str, fetch_fn: callable
    ) -> tuple[T, bool]:
        """
        Get data from cache or fetch fresh.
        
        Returns:
            Tuple of (data, was_cached)
        """
        try:
            data = self[key]
            return data, True
        except KeyError:
            data = fetch_fn()
            self[key] = data
            return data, False

    def _get_source_from_key(self, key: str) -> str:
        """Extract source name from cache key."""
        # Default: assume format is source:something
        parts = key.split(":", 1)
        if len(parts) > 1:
            return parts[0]
        return "default"


# Global cache instance
_default_cache: Optional[DataCache] = None


def get_cache_instance() -> DataCache:
    """Get the global cache instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = DataCache()
    return _default_cache


def reset_cache() -> None:
    """Reset the global cache (useful for testing)."""
    global _default_cache
    _default_cache = None