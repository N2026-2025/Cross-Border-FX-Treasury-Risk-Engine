"""Main engine orchestrator for the FX Treasury Risk Engine."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import structlog

from src.adapters.base import RateAdapterRegistry, get_registry
from src.adapters.fred import FredAdapter
from src.adapters.frankfurter import FrankfurterAdapter
from src.adapters.argentinadatos import ArgentinaDatosAdapter, BCRAAdapter
from src.adapters.coingecko import CoinGeckoAdapter
from src.adapters.indec import INDECAdapter
from src.models.types import (
    ArbitrageSignal,
    Currency,
    DataSource,
    Exposure,
    RateCollection,
)
from src.core.config import get_config
from src.core.arbitrage import ArbitrageEngine, ExposureTracker
from src.cache.layer import get_cache_instance


logger = structlog.get_logger(__name__)


class FXTreasuryEngine:
    """
    Main orchestrator for the Cross-Border FX & Treasury Risk Engine.

    Integrates all data sources, runs arbitrage analysis, and tracks exposure.
    """

    def __init__(self, config: Any | None = None):
        self.config = config or get_config()
        self.registry = get_registry()
        self.cache = get_cache_instance()
        self.arbitrage_engine = ArbitrageEngine(
            spread_threshold_bps=self.config.spread_threshold_bps
        )
        self.exposure_tracker = ExposureTracker(base_currency=Currency.USD)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all data source adapters."""
        if self._initialized:
            return

        # Initialize FRED adapter
        if fred_config := self.config.sources.get("FRED"):
            if fred_config.api_key:
                fred = FredAdapter(
                    api_key=fred_config.api_key,
                    timeout=fred_config.timeout_seconds,
                    retries=fred_config.retries,
                    cache=self.cache,
                )
                self.registry.register(fred)
                self.cache.set_source_ttl("FRED", fred_config.cache_ttl_seconds)

        # Initialize Frankfurter adapter
        if frank_config := self.config.sources.get("FRANKFURTER"):
            frank = FrankfurterAdapter(
                timeout=frank_config.timeout_seconds,
                retries=frank_config.retries,
                cache=self.cache,
            )
            self.registry.register(frank)
            self.cache.set_source_ttl("FRANKFURTER", frank_config.cache_ttl_seconds)

        # Initialize ArgentinaDatos adapter
        if ad_config := self.config.sources.get("ARGENTINA_DATOS"):
            ad = ArgentinaDatosAdapter(
                api_key=ad_config.api_key,
                timeout=ad_config.timeout_seconds,
                retries=ad_config.retries,
                cache=self.cache,
            )
            self.registry.register(ad)
            self.cache.set_source_ttl("ARGENTINA_DATOS", ad_config.cache_ttl_seconds)

        # Initialize BCRA adapter
        if bcra_config := self.config.sources.get("BCRA"):
            bcra = BCRAAdapter(
                api_key=bcra_config.api_key,
                timeout=bcra_config.timeout_seconds,
                retries=bcra_config.retries,
                cache=self.cache,
            )
            self.registry.register(bcra)
            self.cache.set_source_ttl("BCRA", bcra_config.cache_ttl_seconds)

        # Initialize CoinGecko adapter
        if cg_config := self.config.sources.get("COINGECKO"):
            cg = CoinGeckoAdapter(
                api_key=cg_config.api_key,
                timeout=cg_config.timeout_seconds,
                retries=cg_config.retries,
                cache=self.cache,
            )
            self.registry.register(cg)
            self.cache.set_source_ttl("COINGECKO", cg_config.cache_ttl_seconds)

        # Initialize INDEC adapter
        if indec_config := self.config.sources.get("INDEC"):
            indec = INDECAdapter(
                api_key=indec_config.api_key,
                timeout=indec_config.timeout_seconds,
                retries=indec_config.retries,
                cache=self.cache,
            )
            self.registry.register(indec)
            self.cache.set_source_ttl("INDEC", indec_config.cache_ttl_seconds)

        self._initialized = True
        logger.info("FX Treasury Engine initialized", sources=len(self.registry.get_all()))

    async def fetch_all_rates(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> list[RateCollection]:
        """Fetch rates from all registered sources."""
        if not self._initialized:
            await self.initialize()

        if targets is None:
            targets = [
                Currency.EUR,
                Currency.BRL,
                Currency.MXN,
                Currency.ARS,
            ]

        collections: list[RateCollection] = []

        # Fetch from all adapters concurrently
        import asyncio

        async def fetch_from_adapter(adapter):
            try:
                return await adapter.fetch_rates(base, targets)
            except Exception as e:
                logger.error(
                    "Adapter fetch failed",
                    source=adapter.source.value,
                    error=str(e),
                )
                return RateCollection(
                    source=adapter.source,
                    rates=[],
                    fetched_at=datetime.utcnow(),
                    success=False,
                    error=str(e),
                )

        tasks = [fetch_from_adapter(a) for a in self.registry.get_all()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, RateCollection):
                collections.append(result)
            elif isinstance(result, Exception):
                logger.error("Unexpected error", error=str(result))

        return collections

    async def run_analysis(
        self,
        base: Currency = Currency.USD,
        targets: list[Currency] | None = None,
    ) -> dict[str, Any]:
        """
        Run full analysis pipeline: fetch rates, detect arbitrage, track exposure.

        Returns:
            Dictionary with all analysis results
        """
        start_time = datetime.utcnow()

        # Fetch rates
        collections = await self.fetch_all_rates(base, targets)

        # Run arbitrage analysis
        arbitrage_signals = self.arbitrage_engine.analyze_rates(collections, base, targets)

        # Check stablecoin arbitrage
        coingecko_rates = [
            r for c in collections if c.source == DataSource.COINGECKO for r in c.rates
        ]
        fx_rates = [
            r
            for c in collections
            if c.source in [DataSource.ARGENTINA_DATOS, DataSource.BCRA]
            for r in c.rates
        ]
        stablecoin_signals = self.arbitrage_engine.check_stablecoin_arbitrage(
            coingecko_rates, fx_rates
        )

        all_signals = arbitrage_signals + stablecoin_signals

        # Build results
        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "elapsed_seconds": elapsed,
            "collections": collections,
            "arbitrage_signals": all_signals,
            "exposure": self.exposure_tracker.get_total_exposure(),
            "inflation_adjusted_exposure": self.exposure_tracker.get_inflation_adjusted_exposure(),
            "source_count": len(collections),
            "signal_count": len(all_signals),
        }

    async def add_position(
        self,
        currency: Currency,
        amount: Decimal,
        exchange_rate: Decimal,
        inflation_rate: Decimal = Decimal("0"),
    ) -> Exposure:
        """Add a treasury position for exposure tracking."""
        return self.exposure_tracker.add_position(
            currency, amount, exchange_rate, inflation_rate
        )

    async def get_margin_risk(
        self,
        revenue_local: Decimal,
        revenue_currency: Currency,
        current_rate: Decimal,
        inflation_rate: Decimal,
        months_to_settlement: int = 1,
    ) -> dict[str, Decimal]:
        """Calculate margin at risk for foreign currency revenue."""
        return self.exposure_tracker.get_margin_at_risk(
            revenue_local,
            revenue_currency,
            current_rate,
            inflation_rate,
            months_to_settlement,
        )

    async def shutdown(self) -> None:
        """Clean shutdown of all adapters."""
        await self.registry.close_all()
        logger.info("FX Treasury Engine shutdown complete")


# Singleton instance
_engine: Optional[FXTreasuryEngine] = None


async def get_engine() -> FXTreasuryEngine:
    """Get or create the global engine instance."""
    global _engine
    if _engine is None:
        _engine = FXTreasuryEngine()
        await _engine.initialize()
    return _engine


async def reset_engine() -> None:
    """Reset the global engine (useful for testing)."""
    global _engine
    if _engine:
        await _engine.shutdown()
    _engine = None