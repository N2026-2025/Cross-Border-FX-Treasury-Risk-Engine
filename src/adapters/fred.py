"""FRED API adapter for Federal Reserve rates."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog

from httpx import Response

from src.adapters.base import BaseAdapter, DataSource, Currency, Rate, RateType
from src.models.types import RateCollection

logger = structlog.get_logger(__name__)


class FredAdapter(BaseAdapter):
    """Adapter for FRED (Federal Reserve Bank of St. Louis) API."""

    FRED_SERIES_IDS = {
        "FED_FUNDS_RATE": "FEDFUNDS",  # Federal Funds Rate
        "CPI_U": "CPIAUCSL",  # CPI Urban Consumers
        "TREASURY_YIELD_10Y": "DGS10",  # 10-Year Treasury Yield
        "TREASURY_YIELD_2Y": "DGS2",  # 2-Year Treasury Yield
    }

    def __init__(self, api_key: str, **kwargs: Any):
        super().__init__(
            source=DataSource.FRED,
            base_url="https://api.stlouisfed.org/fred",
            api_key=api_key,
            **kwargs,
        )

    async def fetch_rates(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> RateCollection:
        """Fetch rates from FRED API."""
        if targets is None:
            targets = [Currency.USD]

        rates: list[Rate] = []

        # Fetch Federal Funds Rate
        try:
            fed_funds_rate = await self._fetch_fed_funds_rate()
            rates.append(
                self._create_rate(
                    base,
                    base,
                    fed_funds_rate,
                    rate_type=RateType.SPOT,
                    metadata={"description": "Federal Funds Rate"},
                )
            )
        except Exception as e:
            logger.warning("Failed to fetch FED funds rate", error=str(e))

        # Fetch CPI
        try:
            cpi = await self._fetch_cpi()
            rates.append(
                self._create_rate(
                    Currency.USD,
                    Currency.USD,
                    cpi,
                    rate_type=RateType.SPOT,
                    metadata={"description": "US CPI Urban Consumers"},
                )
            )
        except Exception as e:
            logger.warning("Failed to fetch FRED CPI", error=str(e))

        # Fetch Treasury yields
        try:
            yield_10y = await self._fetch_treasury_yield("10Y")
            rates.append(
                self._create_rate(
                    base,
                    base,
                    yield_10y,
                    rate_type=RateType.SPOT,
                    metadata={"description": "10-Year Treasury Yield"},
                )
            )
        except Exception as e:
            logger.warning("Failed to fetch 10Y Treasury yield", error=str(e))

        return RateCollection(
            source=self.source,
            rates=rates,
            fetched_at=datetime.utcnow(),
            success=True,
        )

    async def _fetch_fed_funds_rate(self) -> Decimal:
        """Fetch Federal Funds Rate from FRED."""
        response = await self._request(
            "GET",
            "/series/observations",
            params={
                "series_id": self.FRED_SERIES_IDS["FED_FUNDS_RATE"],
                "api_key": self.api_key,
                "observation_start": (datetime.utcnow().replace(day=1) - timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                ),
                "observation_end": datetime.utcnow().strftime("%Y-%m-%d"),
                "frequency": "daily",
                "frequency": "w",
                "downtype": "lastObservation",
                "aggregation_method": "avg",
            },
        )
        data = response.json()
        observations = data.get("observations", [])
        if observations:
            value = Decimal(observations[0].get("value", "0"))
            return value / 1000  # FRED reports in percent basis points
        return Decimal("0")

    async def _fetch_cpi(self) -> Decimal:
        """Fetch CPI from FRED."""
        response = await self._request(
            "GET",
            "/series/observations",
            params={
                "series_id": self.FRED_SERIES_IDS["CPI_U"],
                "api_key": self.api_key,
                "observation_start": (datetime.utcnow().replace(day=1) - timedelta(days=30)).strftime(
                    "%Y-%m-%d"
                ),
                "observation_end": datetime.utcnow().strftime("%Y-%m-%d"),
                "frequency": "m",
                "frequency": "d",
                "downtype": "lastObservation",
            },
        )
        data = response.json()
        observations = data.get("observations", [])
        if observations:
            value = Decimal(observations[0].get("value", "0"))
            return value / 1000  # FRED indexes, calculate % change
        return Decimal("0")

    async def _fetch_treasury_yield(self, term: str) -> Decimal:
        """Fetch Treasury yield from FRED."""
        series_map = {"10Y": "DGS10", "2Y": "DGS2"}
        series_id = series_map.get(term, "DGS10")

        response = await self._request(
            "GET",
            "/series/observations",
            params={
                "series_id": series_id,
                "api_key": self.api_key,
                "observation_start": (datetime.utcnow().replace(day=1) - timedelta(days=365)).strftime(
                    "%Y-%m-%d"
                ),
                "observation_end": datetime.utcnow().strftime("%Y-%m-%d"),
                "frequency": "d",
                "downtype": "lastObservation",
            },
        )
        data = response.json()
        observations = data.get("observations", [])
        if observations:
            value = Decimal(observations[0].get("value", "0"))
            return value / 100  # FRED yields are in percent
        return Decimal("0")