"""INDEC / Datos Argentina API adapter for inflation data."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from src.adapters.base import BaseAdapter, DataSource, Currency, Rate, RateType
from src.models.types import RateCollection

logger = structlog.get_logger(__name__)


class INDECAdapter(BaseAdapter):
    """Adapter for INDEC (Instituto Nacional de Estadística) / Datos Argentina API."""

    def __init__(self, api_key: str | None = None, **kwargs: Any):
        super().__init__(
            source=DataSource.INDEC,
            base_url="https://apis.datos.gob.ar/series/api",
            api_key=api_key,
            **kwargs,
        )

    async def fetch_rates(
        self,
        base: Currency = Currency.ARS,
        targets: list[Currency] | None = None,
    ) -> RateCollection:
        """Fetch inflation and economic indicators from INDEC."""
        rates: list[Rate] = []

        # Fetch monthly CPI (IPC - Índice de Precios al Consumidor)
        try:
            cpi = await self._fetch_cpi()
            if cpi:
                rates.append(
                    self._create_rate(
                        Currency.ARS,
                        Currency.ARS,
                        cpi,
                        rate_type=RateType.SPOT,
                        metadata={"description": "IPC Mensual (Inflation)", "unit": "percent_change"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch INDEC CPI", error=str(e))

        # Fetch annualized inflation
        try:
            annual_cpi = await self._fetch_annual_cpi()
            if annual_cpi:
                rates.append(
                    self._create_rate(
                        Currency.ARS,
                        Currency.ARS,
                        annual_cpi,
                        rate_type=RateType.SPOT,
                        metadata={"description": "IPC Anual (Annual Inflation)", "unit": "percent_change"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch INDEC annual CPI", error=str(e))

        # Fetch real wage index (for purchasing power analysis)
        try:
            real_wage = await self._fetch_real_wage_index()
            if real_wage:
                rates.append(
                    self._create_rate(
                        Currency.ARS,
                        Currency.ARS,
                        real_wage,
                        rate_type=RateType.SPOT,
                        metadata={"description": "Salario Real Index", "unit": "index"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch INDEC real wage", error=str(e))

        # Fetch wholesale price index
        try:
            ipm = await self._fetch_wholesale_price_index()
            if ipm:
                rates.append(
                    self._create_rate(
                        Currency.ARS,
                        Currency.ARS,
                        ipm,
                        rate_type=RateType.SPOT,
                        metadata={"description": "IPM (Wholesale Price Index)"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch INDEC IPM", error=str(e))

        return RateCollection(
            source=self.source,
            rates=rates,
            fetched_at=datetime.utcnow(),
            success=True,
        )

    async def _fetch_cpi(self) -> Decimal | None:
        """Fetch monthly CPI (IPC) from INDEC."""
        try:
            response = await self._request(
                "GET",
                "/series",
                params={
                    "id": "ipc.1",
                    "format": "json",
                },
            )
            data = response.json()
            if data and "data" in data and len(data["data"]) > 1:
                # Calculate percentage change from last month
                latest = Decimal(str(data["data"][0].get("value", "0")))
                previous = Decimal(str(data["data"][1].get("value", "0")))
                if previous != 0:
                    change = ((latest - previous) / previous) * Decimal("100")
                    return change
        except Exception:
            pass
        return None

    async def _fetch_annual_cpi(self) -> Decimal | None:
        """Fetch annual CPI (IPC anual) from INDEC."""
        try:
            response = await self._request(
                "GET",
                "/series",
                params={
                    "id": "ipc.2",
                    "format": "json",
                },
            )
            data = response.json()
            if data and "data" in data:
                values = [Decimal(str(item.get("value", "0"))) for item in data["data"]]
                if len(values) >= 2:
                    # Sum last 12 months
                    recent_values = values[-12:] if len(values) >= 12 else values
                    return sum(recent_values)
        except Exception:
            pass
        return None

    async def _fetch_real_wage_index(self) -> Decimal | None:
        """Fetch real wage index from INDEC."""
        try:
            response = await self._request(
                "GET",
                "/series",
                params={
                    "id": "remuneracion.3",
                    "format": "json",
                },
            )
            data = response.json()
            if data and "data" in data and len(data["data"]) > 0:
                latest = Decimal(str(data["data"][0].get("value", "0")))
                return latest
        except Exception:
            pass
        return None

    async def _fetch_wholesale_price_index(self) -> Decimal | None:
        """Fetch wholesale price index (IPM) from INDEC."""
        try:
            response = await self._request(
                "GET",
                "/series",
                params={
                    "id": "ipm.1",
                    "format": "json",
                },
            )
            data = response.json()
            if data and "data" in data and len(data["data"]) > 0:
                latest = Decimal(str(data["data"][0].get("value", "0")))
                return latest
        except Exception:
            pass
        return None