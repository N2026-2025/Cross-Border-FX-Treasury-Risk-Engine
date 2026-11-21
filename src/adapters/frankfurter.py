"""Frankfurter Exchange Rates API adapter (ECB rates)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from src.adapters.base import BaseAdapter, DataSource, Currency, Rate, RateType
from src.models.types import RateCollection

logger = structlog.get_logger(__name__)


class FrankfurterAdapter(BaseAdapter):
    """Adapter for Frankfurter Exchange Rates API (ECB)."""

    def __init__(self, **kwargs: Any):
        super().__init__(
            source=DataSource.FRANKFURTER,
            base_url="https://api.frankfurter.app",
            **kwargs,
        )

    async def fetch_rates(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> RateCollection:
        """Fetch rates from Frankfurter API."""
        if targets is None:
            targets = [Currency.EUR, Currency.BRL, Currency.MXN]

        # Frankfurter uses ISO codes, so we need to map
        target_map = {
            Currency.USD: "USD",
            Currency.EUR: "EUR",
            Currency.BRL: "BRL",
            Currency.MXN: "MXN",
            Currency.ARS: "ARS",
        }

        targets_str = ",".join([target_map.get(t, t.value) for t in targets])
        base_str = target_map.get(base, base.value)

        try:
            response = await self._request(
                "GET",
                "/latest",
                params={"from": base_str, "to": targets_str},
            )
            data = response.json()

            rates: list[Rate] = []
            for target in targets:
                target_rate = data.get("rates", {}).get(target.value)
                if target_rate is not None:
                    rates.append(
                        self._create_rate(
                            base,
                            target,
                            Decimal(str(target_rate)),
                            rate_type=RateType.OFFICIAL,
                            metadata={"source_api": "Frankfurter/ECB"},
                        )
                    )

            return RateCollection(
                source=self.source,
                rates=rates,
                fetched_at=datetime.utcnow(),
                success=True,
            )
        except Exception as e:
            return RateCollection(
                source=self.source,
                rates=[],
                fetched_at=datetime.utcnow(),
                success=False,
                error=str(e),
            )

    async def fetch_latest_rate(
        self,
        base: Currency = Currency.EUR,
        target: Currency = Currency.USD,
    ) -> Decimal | None:
        """Fetch a single latest rate."""
        target_map = {
            Currency.USD: "USD",
            Currency.EUR: "EUR",
            Currency.BRL: "BRL",
            Currency.MXN: "MXN",
            Currency.ARS: "ARS",
        }

        base_str = target_map.get(base, base.value)
        target_str = target_map.get(target, target.value)

        try:
            response = await self._request(
                "GET",
                "/latest",
                params={"from": base_str, "to": target_str},
            )
            data = response.json()
            rate = data.get("rates", {}).get(target_str)
            if rate is not None:
                return Decimal(str(rate))
        except Exception:
            pass
        return None