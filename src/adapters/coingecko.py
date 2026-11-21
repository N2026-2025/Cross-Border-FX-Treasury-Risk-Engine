"""CoinGecko API adapter for stablecoin data."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from src.adapters.base import BaseAdapter, DataSource, Currency, Rate, RateType
from src.models.types import RateCollection

logger = structlog.get_logger(__name__)


class CoinGeckoAdapter(BaseAdapter):
    """Adapter for CoinGecko Public API (stablecoins and crypto)."""

    def __init__(self, api_key: str | None = None, **kwargs: Any):
        super().__init__(
            source=DataSource.COINGECKO,
            base_url="https://api.coingecko.com/api/v3",
            api_key=api_key,
            **kwargs,
        )

    async def fetch_rates(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> RateCollection:
        """Fetch stablecoin rates from CoinGecko."""
        if targets is None:
            targets = [Currency.USDT, Currency.USDC]

        rates: list[Rate] = []

        # Fetch USDT/USDC price vs USD
        try:
            coin_prices = await self._fetch_simple_price()
            for target in targets:
                coin_id = self._currency_to_coin_id(target)
                if coin_id:
                    usd_price = coin_prices.get(coin_id, {}).get("usd")
                    if usd_price is not None:
                        rates.append(
                            self._create_rate(
                                Currency.USD,
                                target,
                                Decimal(str(usd_price)),
                                rate_type=RateType.SPOT,
                                metadata={"coin_id": coin_id},
                            )
                        )
        except Exception as e:
            logger.warning("Failed to fetch CoinGecko prices", error=str(e))

        # Fetch liquidity metrics
        try:
            liquidity = await self._fetch_global_data()
            if liquidity:
                rates.append(
                    self._create_rate(
                        Currency.USD,
                        Currency.USDT,
                        Decimal(str(liquidity)),
                        rate_type=RateType.SPOT,
                        metadata={"description": "Total crypto market cap USD"},
                    )
                )
        except Exception as e:
            logger.warning("Failed to fetch CoinGecko global data", error=str(e))

        return RateCollection(
            source=self.source,
            rates=rates,
            fetched_at=datetime.utcnow(),
            success=True,
        )

    def _currency_to_coin_id(self, currency: Currency) -> str | None:
        """Map currency to CoinGecko coin ID."""
        mapping = {
            Currency.USDT: "tether",
            Currency.USDC: "usd-coin",
        }
        return mapping.get(currency)

    async def _fetch_simple_price(self) -> dict[str, dict[str, float]]:
        """Fetch simple price from CoinGecko."""
        ids = "tether,usd-coin"
        response = await self._request(
            "GET",
            "/simple/price",
            params={"ids": ids, "vs_currencies": "usd"},
        )
        return response.json()

    async def _fetch_global_data(self) -> Decimal | None:
        """Fetch global crypto market data."""
        try:
            response = await self._request(
                "GET",
                "/global",
            )
            data = response.json()
            market_cap = data.get("data", {}).get("total_market_cap", {}).get("usd")
            if market_cap is not None:
                return Decimal(str(market_cap))
        except Exception:
            pass
        return None

    async def fetch_stablecoin_peg_deviation(
        self, coin: Currency = Currency.USDT
    ) -> Decimal | None:
        """Calculate peg deviation from $1.00 USD."""
        try:
            coin_id = self._currency_to_coin_id(coin)
            if not coin_id:
                return None
            response = await self._request(
                "GET",
                "/simple/price",
                params={"ids": coin_id, "vs_currencies": "usd"},
            )
            data = response.json()
            price = Decimal(str(data.get(coin_id, {}).get("usd", "0")))
            deviation = price - Decimal("1.00")
            return deviation
        except Exception:
            return None