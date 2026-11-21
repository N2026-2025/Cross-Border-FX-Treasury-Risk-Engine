"""ArgentinaDatos & BCRA API adapter for local FX rates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from src.adapters.base import BaseAdapter, DataSource, Currency, Rate, RateType
from src.models.types import RateCollection

logger = structlog.get_logger(__name__)


class ArgentinaDatosAdapter(BaseAdapter):
    """Adapter for ArgentinaDatos API (Argentinian market data)."""

    def __init__(self, api_key: str | None = None, **kwargs: Any):
        super().__init__(
            source=DataSource.ARGENTINA_DATOS,
            base_url="https://api.argentinadatos.com/v1",
            api_key=api_key,
            **kwargs,
        )

    async def fetch_rates(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> RateCollection:
        """Fetch rates from ArgentinaDatos API."""
        if targets is None:
            targets = [Currency.ARS]

        rates: list[Rate] = []

        # Fetch blue dollar (dolar blue) rate
        try:
            blue_rate = await self._fetch_blue_dollar()
            if blue_rate:
                rates.append(
                    self._create_rate(
                        Currency.USD,
                        Currency.ARS,
                        blue_rate,
                        rate_type=RateType.BLUE,
                        metadata={"description": "Dólar Blue (parallel market)"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch blue dollar", error=str(e))

        # Fetch official dollar rate
        try:
            official_rate = await self._fetch_official_dollar()
            if official_rate:
                rates.append(
                    self._create_rate(
                        Currency.USD,
                        Currency.ARS,
                        official_rate,
                        rate_type=RateType.OFFICIAL,
                        metadata={"description": "Dólar Oficial"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch official dollar", error=str(e))

        # Fetch financial dollar (MEP/CCL)
        try:
            financial_rate = await self._fetch_financial_dollar()
            if financial_rate:
                rates.append(
                    self._create_rate(
                        Currency.USD,
                        Currency.ARS,
                        financial_rate,
                        rate_type=RateType.FINANCIAL,
                        metadata={"description": "Dólar Financiero (MEP/CCL)"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch financial dollar", error=str(e))

        return RateCollection(
            source=self.source,
            rates=rates,
            fetched_at=datetime.utcnow(),
            success=True,
        )

    async def _fetch_blue_dollar(self) -> Decimal | None:
        """Fetch Dólar Blue rate from ArgentinaDatos."""
        try:
            response = await self._request(
                "GET",
                "/finanzas/dolar/blue",
            )
            data = response.json()
            if data.get("success") and data.get("data"):
                return Decimal(str(data["data"].get("venta", "0")))
        except Exception:
            pass
        return None

    async def _fetch_official_dollar(self) -> Decimal | None:
        """Fetch Dólar Oficial rate from ArgentinaDatos."""
        try:
            response = await self._request(
                "GET",
                "/finanzas/dolar/oficial",
            )
            data = response.json()
            if data.get("success") and data.get("data"):
                return Decimal(str(data["data"].get("venta", "0")))
        except Exception:
            pass
        return None

    async def _fetch_financial_dollar(self) -> Decimal | None:
        """Fetch Dólar Financiero (MEP/CCL) rate from ArgentinaDatos."""
        try:
            response = await self._request(
                "GET",
                "/finanzas/dolar/financiero",
            )
            data = response.json()
            if data.get("success") and data.get("data"):
                return Decimal(str(data["data"].get("venta", "0")))
        except Exception:
            pass
        return None


class BCRAAdapter(BaseAdapter):
    """Adapter for BCRA (Banco Central de la República Argentina) API."""

    def __init__(self, api_key: str | None = None, **kwargs: Any):
        super().__init__(
            source=DataSource.BCRA,
            base_url="https://apis.bcra.gob.ar",
            api_key=api_key,
            **kwargs,
        )

    async def fetch_rates(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> RateCollection:
        """Fetch rates from BCRA API."""
        if targets is None:
            targets = [Currency.ARS]

        rates: list[Rate] = []

        # Fetch official exchange rate (comunicación A 3500)
        try:
            official_rate = await self._fetch_official_rate()
            if official_rate:
                rates.append(
                    self._create_rate(
                        Currency.USD,
                        Currency.ARS,
                        official_rate,
                        rate_type=RateType.OFFICIAL,
                        metadata={"source": "BCRA Comunicación A 3500"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch BCRA official rate", error=str(e))

        # Fetch reserves
        try:
            reserves = await self._fetch_reserves()
            if reserves:
                rates.append(
                    self._create_rate(
                        Currency.USD,
                        Currency.ARS,
                        reserves,
                        rate_type=RateType.OFFICIAL,
                        metadata={"description": "International Reserves (USD millions)"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch BCRA reserves", error=str(e))

        # Fetch interest rate (tasa de política monetaria)
        try:
            policy_rate = await self._fetch_policy_rate()
            if policy_rate:
                rates.append(
                    self._create_rate(
                        Currency.ARS,
                        Currency.ARS,
                        policy_rate,
                        rate_type=RateType.OFFICIAL,
                        metadata={"description": "BCRA Policy Rate (TNA)"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch BCRA policy rate", error=str(e))

        return RateCollection(
            source=self.source,
            rates=rates,
            fetched_at=datetime.utcnow(),
            success=True,
        )

    async def _fetch_official_rate(self) -> Decimal | None:
        """Fetch official USD/ARS rate from BCRA."""
        try:
            response = await self._request(
                "GET",
                "/estadisticas/v1.0/dolar/oficial",
            )
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                latest = data[-1]
                if "v" in latest:
                    return Decimal(str(latest["v"]))
        except Exception:
            pass
        return None

    async def _fetch_reserves(self) -> Decimal | None:
        """Fetch international reserves from BCRA."""
        try:
            response = await self._request(
                "GET",
                "/estadisticas/v1.0/reservas",
            )
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                latest = data[-1]
                if "v" in latest:
                    return Decimal(str(latest["v"]))
        except Exception:
            pass
        return None

    async def _fetch_policy_rate(self) -> Decimal | None:
        """Fetch BCRA monetary policy rate."""
        try:
            response = await self._request(
                "GET",
                "/estadisticas/v1.0/tasas/politica-monetaria",
            )
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                latest = data[-1]
                if "v" in latest:
                    return Decimal(str(latest["v"]))
        except Exception:
            pass
        return None