"""Rate normalization and spread calculation logic."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.models.types import Currency, DataSource, Rate, RateCollection, RateType, Spread


class RateNormalizer:
    """Normalizes rates across multiple sources to a common base currency (USD)."""

    def __init__(self, base_currency: Currency = Currency.USD):
        self.base_currency = base_currency

    def to_base(
        self,
        source: DataSource,
        base: Currency,
        target: Currency,
        rate: Decimal,
    ) -> Decimal:
        """
        Convert a rate to the base currency.

        Rates are expressed as: 1 base_currency = target_currency * rate
        We need to convert to: 1 base_currency = target_currency * (rate / inverse_rate)
        """
        if base == self.base_currency:
            return rate
        if target == self.base_currency:
            return Decimal("1") / rate
        # For cross rates, we'd need cross-rate calculation
        # For simplicity, assume via base currency: 1 USD = rate
        return Decimal("1") / rate

    def calculate_spread(
        self,
        rate_a: Rate,
        rate_b: Rate,
    ) -> Decimal:
        """
        Calculate spread in basis points between two rates.

        Positive spread: rate_a - rate_b (buying cheaper through source B, selling through A)
        Negative spread: rate_b - rate_a
        """
        spread = rate_a.rate - rate_b.rate
        spread_bps = abs(spread) * Decimal("10000") / Decimal("1")
        return spread_bps

    def determine_arbitrage_direction(
        self,
        rate_a: Rate,
        rate_b: Rate,
    ) -> str:
        """
        Determine buy/sell signal based on rate comparison.

        If rate_a > rate_b, we can BUY at rate_b and SELL at rate_a (profit).
        If rate_b > rate_a, we can BUY at rate_a and SELL at rate_b (profit).
        """
        if rate_a.rate > rate_b.rate:
            return "BUY_AT_B_SELL_AT_A"
        elif rate_b.rate > rate_a.rate:
            return "BUY_AT_A_SELL_AT_B"
        return "NO_OPPORTUNITY"

    def normalize_collection(
        self,
        collections: list[RateCollection],
    ) -> RateCollection:
        """
        Normalize a collection of rate collections from multiple sources.
        Returns the most recent valid rate per source-pair.
        """
        # Implementation would aggregate and pick latest
        # This is a stub for now
        return collections[0]


class SpreadCalculator:
    """Calculates arbitrage spreads and signals."""

    def __init__(self, threshold_bps: Decimal = Decimal("50")):
        self.threshold_bps = threshold_bps
        self.last_calculation: Optional[datetime] = None

    def calculate_spread_between(
        self,
        source_a: DataSource,
        source_b: DataSource,
        base: Currency,
        target: Currency,
        rate_a: Rate,
        rate_b: Rate,
    ) -> Spread:
        """
        Calculate arbitrage spread between two sources.

        Returns:
            Spread with direction and basis points value
        """
        spread_value = abs(rate_a.rate - rate_b.rate)
        spread_bps = spread_value * Decimal("10000") / rate_a.rate

        if spread_value > self.threshold_bps / Decimal("10000"):
            direction = self.determine_arbitrage_direction(rate_a, rate_b)
        else:
            direction = "NO_OPPORTUNITY"

        return Spread(
            source_a=source_a,
            source_b=source_b,
            base_currency=base,
            target_currency=target,
            rate_a=rate_a.rate,
            rate_b=rate_b.rate,
            spread_bps=spread_bps,
            direction=direction,
            timestamp=rate_a.timestamp,
        )

    def determine_arbitrage_direction(
        self,
        rate_a: Rate,
        rate_b: Rate,
    ) -> str:
        """
        Determine buy/sell direction based on rate comparison.

        If rate_a > rate_b, BUY at rate_b (source B), SELL at rate_a (source A)
        If rate_b > rate_a, BUY at rate_a (source A), SELL at rate_b (source B)
        """
        if rate_a.rate > rate_b.rate:
            return "BUY_AT_B_SELL_AT_A"
        elif rate_b.rate > rate_a.rate:
            return "BUY_AT_A_SELL_AT_B"
        return "NO_OPPORTUNITY"


class InflationAdjuster:
    """Adjusts real amounts for inflation using CPI data."""

    def __init__(self, cpi_series: list[tuple[Decimal, Decimal]] | None = None):
        # list of (index, base_index) tuples or actual CPI values
        self.cpi_series = cpi_series or []

    def calculate_real_return(
        self,
        nominal_return: Decimal,
        cpi_ratio: Decimal,
    ) -> Decimal:
        """
        Calculate real return using Fisher approximation:
        Real = (1 + Nominal) / (1 + inflation) - 1
        """
        if cpi_ratio <= Decimal("0"):
            return nominal_return
        real_return = (Decimal("1") + nominal_return) / (Decimal("1") + cpi_ratio) - Decimal("1")
        return real_return

    def adjust_amount(
        self,
        amount: Decimal,
        inflation_rate: Decimal,
        months: int = 12,
    ) -> Decimal:
        """
        Adjust amount for inflation over given months.

        amount_real = amount_nominal * (1 - inflation_rate)^months
        """
        inflation_factor = (Decimal("1") - inflation_rate) ** months
        return amount * inflation_factor
