"""Base adapter class for all data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.types import Currency, DataSource, Rate, RateCollection, RateType
from src.cache.layer import DataCache, get_cache_instance


logger = structlog.get_logger(__name__)


class BaseAdapter(ABC):
    """Abstract base class for data source adapters."""

    def __init__(
        self,
        source: DataSource,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
        retries: int = 3,
        cache: DataCache | None = None,
    ):
        self.source = source
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.cache = cache or get_cache_instance()
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with retry logic."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                base_url=self.base_url,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic."""
        final_headers = headers or {}
        if self.api_key:
            final_headers["Authorization"] = f"Bearer {self.api_key}"

        response = await self.client.request(
            method, endpoint, params=params, headers=final_headers
        )
        response.raise_for_status()
        return response

    @abstractmethod
    async def fetch_rates(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> RateCollection:
        """Fetch current exchange rates from the source."""
        pass

    def _create_rate(
        self,
        base: Currency,
        target: Currency,
        rate_value: str | float | Decimal,
        rate_type: RateType = RateType.MID_MARKET,
        metadata: dict[str, Any] | None = None,
    ) -> Rate:
        """Create a Rate object with proper Decimal precision."""
        return Rate(
            source=self.source,
            base_currency=base,
            target_currency=target,
            rate=Decimal(str(rate_value)),
            rate_type=rate_type,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        )

    async def fetch_cached(
        self,
        cache_key: str,
        fetch_fn: callable,
    ) -> RateCollection:
        """Fetch data with caching."""
        cached, was_cached = self.cache.get_with_ttl(
            cache_key, self.source.value, fetch_fn
        )
        if was_cached:
            logger.debug("Cache hit", source=self.source.value, key=cache_key)
        else:
            logger.debug("Cache miss", source=self.source.value, key=cache_key)
        return cached


class RateAdapterRegistry:
    """Registry for managing all rate adapters."""

    def __init__(self):
        self._adapters: dict[DataSource, BaseAdapter] = {}

    def register(self, adapter: BaseAdapter) -> None:
        """Register an adapter."""
        self._adapters[adapter.source] = adapter

    def get(self, source: DataSource) -> BaseAdapter | None:
        """Get an adapter by source."""
        return self._adapters.get(source)

    def get_all(self) -> list[BaseAdapter]:
        """Get all registered adapters."""
        return list(self._adapters.values())

    async def close_all(self) -> None:
        """Close all adapter HTTP clients."""
        for adapter in self._adapters.values():
            await adapter.close()


# Global registry
_registry: RateAdapterRegistry | None = None


def get_registry() -> RateAdapterRegistry:
    """Get the global adapter registry."""
    global _registry
    if _registry is None:
        _registry = RateAdapterRegistry()
    return _registry