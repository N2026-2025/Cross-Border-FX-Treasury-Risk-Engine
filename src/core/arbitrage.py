"""Arbitrage engine for multi-source FX arbitrage detection."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import structlog

from src.models.types import (
    ArbitrageSignal,
    Currency,
    DataSource,
    Exposure,
    Rate,
    RateCollection,
    RateType,
    Spread,
)
from src.core.normalization import SpreadCalculator, InflationAdjuster, RateNormalizer


logger = structlog.get_logger(__name__)


class ArbitrageEngine:
    """
    Core arbitrage engine that detects and signals FX arbitrage opportunities
    across multiple data sources.
    """

    def __init__(
        self,
        spread_threshold_bps: Decimal = Decimal("50"),
        min_liquidity_usd: Decimal = Decimal("10000"),
    ):
        self.spread_calculator = SpreadCalculator(spread_threshold_bps)
        self.rate_normalizer = RateNormalizer()
        self.inflation_adjuster = InflationAdjuster()
        self.min_liquidity_usd = min_liquidity_usd
        self.signals: list[ArbitrageSignal] = []

    def analyze_rates(
        self,
        collections: list[RateCollection],
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> list[ArbitrageSignal]:
        """
        Analyze rate collections from multiple sources for arbitrage opportunities.

        Args:
            collections: List of RateCollection from different sources
            base: Base currency for analysis
            targets: Target currencies to check

        Returns:
            List of ArbitrageSignal objects
        """
        if targets is None:
            targets = [
                Currency.EUR,
                Currency.BRL,
                Currency.MXN,
                Currency.ARS,
            ]

        signals: list[ArbitrageSignal] = []

        # Group rates by currency pair
        rates_by_pair: dict[tuple[Currency, Currency], list[Rate]] = {}
        for collection in collections:
            for rate in collection.rates:
                key = (rate.base_currency, rate.target_currency)
                if key not in rates_by_pair:
                    rates_by_pair[key] = []
                rates_by_pair[key].append(rate)

        # Analyze each pair for arbitrage
        for (base_cur, target_cur), rates in rates_by_pair.items():
            if len(rates) < 2:
                continue

            # Compare all pairs of sources
            for i, rate_a in enumerate(rates):
                for rate_b in rates[i + 1 :]:
                    signal = self._evaluate_pair(rate_a, rate_b, base_cur, target_cur)
                    if signal and signal.confidence > Decimal("0.5"):
                        signals.append(signal)
                        logger.info(
                            "Arbitrage signal generated",
                            base=base_cur.value,
                            target=target_cur.value,
                            action=signal.recommended_action,
                            spread_bps=str(signal.spread_bps),
                            confidence=str(signal.confidence),
                        )

        self.signals = signals
        return signals

    def _evaluate_pair(
        self,
        rate_a: Rate,
        rate_b: Rate,
        base: Currency,
        target: Currency,
    ) -> Optional[ArbitrageSignal]:
        """
        Evaluate a pair of rates for arbitrage opportunity.

        Returns:
            ArbitrageSignal if opportunity exists, None otherwise
        """
        spread = self.spread_calculator.calculate_spread_between(
            rate_a.source,
            rate_b.source,
            base,
            target,
            rate_a,
            rate_b,
        )

        # Only signal if spread exceeds threshold
        if spread.spread_bps < self.spread_calculator.threshold_bps:
            return None

        # Calculate confidence based on spread magnitude and source reliability
        confidence = min(spread.spread_bps / Decimal("200"), Decimal("1"))

        # Estimate savings per $1M USD
        expected_savings = (
            Decimal("1000000")
            * spread.spread_bps
            / Decimal("10000")
            * Decimal("0.01")
        )

        # Determine action based on direction
        if spread.direction == "BUY_AT_B_SELL_AT_A":
            recommended_action = f"BUY {target.value} at {rate_b.source.value}, SELL at {rate_a.source.value}"
        elif spread.direction == "BUY_AT_A_SELL_AT_B":
            recommended_action = f"BUY {target.value} at {rate_a.source.value}, SELL at {rate_b.source.value}"
        else:
            recommended_action = "HOLD"

        return ArbitrageSignal(
            base_currency=base,
            target_currency=target,
            recommended_action=recommended_action,
            confidence=confidence,
            spread_bps=spread.spread_bps,
            expected_savings_usd=expected_savings,
            sources=[rate_a.source, rate_b.source],
            timestamp=datetime.utcnow(),
        )

    def check_stablecoin_arbitrage(
        self,
        coingecko_rates: list[Rate],
        fx_rates: list[Rate],
    ) -> list[ArbitrageSignal]:
        """
        Check for arbitrage between stablecoin rates and traditional FX rates.

        E.g., USDT/USD vs USD/ARS blue rate
        """
        signals: list[ArbitrageSignal] = []

        # Get stablecoin prices
        usdt_rate = next(
            (r for r in coingecko_rates if r.target_currency == Currency.USDT), None
        )
        usdc_rate = next(
            (r for r in coingecko_rates if r.target_currency == Currency.USDC), None
        )

        # Get local FX rates (e.g., ARS blue dollar)
        ars_blue = next(
            (
                r
                for r in fx_rates
                if r.target_currency == Currency.ARS and r.rate_type == RateType.BLUE
            ),
            None,
        )

        if usdt_rate and ars_blue:
            # Check if stablecoin provides better conversion
            signal = self._evaluate_stablecoin_route(
                usdt_rate, ars_blue, Currency.USD, Currency.ARS
            )
            if signal:
                signals.append(signal)

        if usdc_rate and ars_blue:
            signal = self._evaluate_stablecoin_route(
                usdc_rate, ars_blue, Currency.USD, Currency.ARS
            )
            if signal:
                signals.append(signal)

        return signals

    def _evaluate_stablecoin_route(
        self,
        stablecoin_rate: Rate,
        fx_rate: Rate,
        base: Currency,
        target: Currency,
    ) -> Optional[ArbitrageSignal]:
        """
        Evaluate if using stablecoin as intermediate provides better rate.
        """
        # For USD/ARS: if USDT/USD ~ 1.0, then USDT/ARS = USD/ARS * USDT/USD
        # Check deviation from peg
        peg_deviation = abs(stablecoin_rate.rate - Decimal("1.00"))
        peg_deviation_bps = peg_deviation * Decimal("10000")

        if peg_deviation_bps > Decimal("100"):  # More than 1% depeg
            return ArbitrageSignal(
                base_currency=base,
                target_currency=target,
                recommended_action=f"WARNING: {stablecoin_rate.target_currency.value} depegged by {peg_deviation_bps} bps",
                confidence=Decimal("0.9"),
                spread_bps=peg_deviation_bps,
                expected_savings_usd=Decimal("0"),
                sources=[DataSource.COINGECKO, fx_rate.source],
                timestamp=datetime.utcnow(),
            )

        return None


class ExposureTracker:
    """Tracks multi-currency treasury exposure with inflation adjustment."""

    def __init__(self, base_currency: Currency = Currency.USD):
        self.base_currency = base_currency
        self.positions: dict[Currency, Exposure] = {}
        self.inflation_adjuster = InflationAdjuster()

    def add_position(
        self,
        currency: Currency,
        amount: Decimal,
        exchange_rate: Decimal,
        inflation_rate: Decimal = Decimal("0"),
    ) -> Exposure:
        """Add or update a currency position."""
        adjusted_amount = amount
        if inflation_rate > Decimal("0"):
            adjusted_amount = self.inflation_adjuster.adjust_amount(
                amount, inflation_rate
            )

        position = Exposure(
            currency=currency,
            amount=amount,
            base_currency=self.base_currency,
            exchange_rate=exchange_rate,
            adjusted_amount=adjusted_amount,
            timestamp=datetime.utcnow(),
        )

        self.positions[currency] = position
        return position

    def get_total_exposure(self) -> dict[str, Decimal]:
        """Get total exposure in base currency."""
        total = Decimal("0")
        by_currency: dict[str, Decimal] = {}

        for currency, position in self.positions.items():
            usd_value = position.amount * position.exchange_rate
            total += usd_value
            by_currency[currency.value] = usd_value

        return {
            "total_usd": total,
            **by_currency,
        }

    def get_inflation_adjusted_exposure(self) -> dict[str, Decimal]:
        """Get inflation-adjusted exposure in base currency."""
        total = Decimal("0")
        by_currency: dict[str, Decimal] = {}

        for currency, position in self.positions.items():
            usd_value = position.adjusted_amount * position.exchange_rate
            total += usd_value
            by_currency[currency.value] = usd_value

        return {
            "total_usd": total,
            **by_currency,
        }

    def calculate_hedge_ratio(
        self,
        target_currency: Currency,
        hedge_percentage: Decimal = Decimal("0.5"),
    ) -> Decimal:
        """
        Calculate how much to hedge for a given currency.

        Returns the notional amount to hedge in base currency.
        """
        position = self.positions.get(target_currency)
        if not position:
            return Decimal("0")

        exposure_usd = position.amount * position.exchange_rate
        return exposure_usd * hedge_percentage

    def get_margin_at_risk(
        self,
        revenue_local: Decimal,
        revenue_currency: Currency,
        current_rate: Decimal,
        inflation_rate: Decimal,
        months_to_settlement: int = 1,
    ) -> dict[str, Decimal]:
        """
        Calculate margin at risk for foreign currency revenue.

        Returns projected real USD value after inflation and FX movement.
        """
        nominal_usd = revenue_local * current_rate
        real_usd = self.inflation_adjuster.adjust_amount(
            nominal_usd, inflation_rate, months_to_settlement
        )

        return {
            "nominal_usd": nominal_usd,
            "real_usd": real_usd,
            "inflation_erosion": nominal_usd - real_usd,
            "months_to_settlement": months_to_settlement,
        }