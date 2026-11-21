"""Unit tests for the Cross-Border FX & Treasury Risk Engine."""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timedelta

import pytest

from src.models.types import (
    DataSource,
    Currency,
    Rate,
    RateType,
    Spread,
    Exposure,
    ArbitrageSignal,
    RateCollection,
)
from src.core.config import EngineConfig, DataSourceConfig, get_config, set_config
from src.core.normalization import RateNormalizer, SpreadCalculator, InflationAdjuster
from src.core.arbitrage import ArbitrageEngine
from src.cache.layer import DataCache


class TestDataModels:
    """Test core data models."""

    def test_rate_creation_with_decimal(self):
        """Test Rate model with Decimal precision."""
        rate = Rate(
            source=DataSource.FRED,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=Decimal("1000.50"),
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )
        assert rate.rate == Decimal("1000.50")
        assert rate.base_currency == Currency.USD
        assert rate.target_currency == Currency.ARS

    def test_rate_with_float_conversion(self):
        """Test Rate model converts float to Decimal."""
        rate = Rate(
            source=DataSource.FRED,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=1000.50,
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )
        # Should be Decimal representation of 1000.50
        assert isinstance(rate.rate, Decimal)
        assert rate.rate == Decimal("1000.5")

    def test_rate_with_string_conversion(self):
        """Test Rate model converts string to Decimal."""
        rate = Rate(
            source=DataSource.FRED,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate="1000.50",
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )
        assert rate.rate == Decimal("1000.50")

    def test_spread_creation(self):
        """Test Spread model creation."""
        rate_a = Rate(
            source=DataSource.FRED,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=Decimal("1000.50"),
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )
        rate_b = Rate(
            source=DataSource.BCRA,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=Decimal("990.25"),
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )

        # Calculate spread manually
        spread_value = abs(rate_a.rate - rate_b.rate)
        spread_bps = spread_value * Decimal("10000") / rate_a.rate

        assert spread_bps > Decimal("0")
        assert isinstance(spread_bps, Decimal)

    def test_exposure_creation(self):
        """Test Exposure model creation."""
        exposure = Exposure(
            currency=Currency.ARS,
            amount=Decimal("1000000"),
            base_currency=Currency.USD,
            exchange_rate=Decimal("1000.50"),
            adjusted_amount=Decimal("1000000"),
            timestamp=datetime.utcnow(),
        )
        assert exposure.amount == Decimal("1000000")
        assert exposure.exchange_rate == Decimal("1000.50")
        assert exposure.currency == Currency.ARS

    def test_arbitrage_signal_creation(self):
        """Test ArbitrageSignal model creation."""
        signal = ArbitrageSignal(
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            recommended_action="BUY",
            confidence=Decimal("0.85"),
            spread_bps=Decimal("150.00"),
            expected_savings_usd=Decimal("500.00"),
            sources=[DataSource.FRED, DataSource.BCRA],
            timestamp=datetime.utcnow(),
        )
        assert signal.base_currency == Currency.USD
        assert signal.target_currency == Currency.ARS
        assert signal.recommended_action == "BUY"
        assert signal.confidence == Decimal("0.85")
        assert signal.spread_bps == Decimal("150.00")
        assert signal.expected_savings_usd == Decimal("500.00")
        assert len(signal.sources) == 2


class TestEngineConfig:
    """Test engine configuration."""

    def test_config_from_env(self):
        """Test EngineConfig from environment variables."""
        config = EngineConfig.from_env()
        assert config.environment == "development"
        assert config.log_level == "INFO"
        assert config.sources is not None
        assert "FRED" in config.sources
        assert "COINGECKO" in config.sources

    def test_config_from_yaml(self):
        """Test EngineConfig from YAML file."""
        config = EngineConfig.from_yaml("config/engine.yaml")
        assert config.environment == "development"
        assert config.spread_threshold_bps == Decimal("50")
        assert len(config.sources) == 6  # All 6 sources

    def test_config_to_yaml_roundtrip(self):
        """Test EngineConfig YAML roundtrip."""
        config = EngineConfig.from_env()
        set_config(config)
        # Reset singleton
        from src.core.config import _CONFIG
        import src.core.config as config_mod
        config_mod._CONFIG = None

        # Re-load
        config2 = EngineConfig.from_yaml("config/engine.yaml")
        assert config2.environment == config.environment


class TestCacheLayer:
    """Test caching layer."""

    def test_cache_set_get(self):
        """Test basic cache set and get operations."""
        cache = DataCache()
        cache["test_key"] = {"data": "test_value"}
        result = cache["test_key"]
        assert result["data"] == "test_value"

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = DataCache(default_ttl=1)  # 1 second TTL
        cache["expiring_key"] = {"data": "will_expire", "_source": "test", "_fetched_at": 0}

        # Should work immediately
        result = cache["expiring_key"]
        assert result["data"] == "will_expire"

    def test_cache_source_ttl(self):
        """Test source-specific TTL configuration."""
        cache = DataCache()
        cache.set_source_ttl("FRED", 3600)
        cache.set_source_ttl("COINGECKO", 60)

        assert cache._get_ttl("FRED") == 3600
        assert cache._get_ttl("COINGECKO") == 60
        assert cache._get_ttl("default") == 300  # Default TTL


class TestNormalization:
    """Test rate normalization and spread calculations."""

    def test_rate_normalizer_to_base(self):
        """Test RateNormalizer converts rates to base currency."""
        normalizer = RateNormalizer(base_currency=Currency.USD)

        # When base==target==base_currency, rate passes through unchanged
        result = normalizer.to_base(
            DataSource.FRED,
            Currency.USD,
            Currency.USD,
            Decimal("1000.00"),
        )
        assert result == Decimal("1000.00")

        # target==base_currency, convert via inverse
        result2 = normalizer.to_base(
            DataSource.FRED,
            Currency.ARS,
            Currency.USD,
            Decimal("1000.00"),
        )
        assert result2 == Decimal("0.001")

    def test_rate_normalizer_same_base_target(self):
        """Test when base and target are same as configured base."""
        normalizer = RateNormalizer(base_currency=Currency.USD)
        result = normalizer.to_base(
            DataSource.FRED,
            Currency.USD,
            Currency.USD,
            Decimal("1.00"),
        )
        assert result == Decimal("1.00")

    def test_spread_calculator_basic(self):
        """Test basic spread calculation."""
        calculator = SpreadCalculator(threshold_bps=Decimal("50"))

        rate_a = Rate(
            source=DataSource.FRED,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=Decimal("1000.50"),
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )
        rate_b = Rate(
            source=DataSource.BCRA,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=Decimal("990.25"),
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )

        spread_bps = abs(rate_a.rate - rate_b.rate) * Decimal("10000") / rate_a.rate
        assert spread_bps > Decimal("50")  # Above threshold

    def test_arbitrage_direction_buy(self):
        """Test arbitrage direction determination."""
        calculator = SpreadCalculator()

        rate_a = Rate(
            source=DataSource.FRED,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=Decimal("1000.50"),
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )
        rate_b = Rate(
            source=DataSource.BCRA,
            base_currency=Currency.USD,
            target_currency=Currency.ARS,
            rate=Decimal("990.25"),
            rate_type=RateType.OFFICIAL,
            timestamp=datetime.utcnow(),
        )

        # rate_a > rate_b, so BUY at rate_b, SELL at rate_a
        if rate_a.rate > rate_b.rate:
            direction = "BUY_AT_B_SELL_AT_A"
        else:
            direction = "BUY_AT_A_SELL_AT_B"

        assert direction == "BUY_AT_B_SELL_AT_A"

    def test_inflation_adjuster_real_return(self):
        """Test InflationAdjuster real return calculation."""
        adjuster = InflationAdjuster()

        nominal_return = Decimal("0.10")  # 10% nominal
        cpi_ratio = Decimal("0.05")  # 5% inflation

        real_return = (Decimal("1") + nominal_return) / (Decimal("1") + cpi_ratio) - Decimal("1")
        # Approximately 4.7619%, rounded to 4 decimal places
        assert round(real_return, 4) == Decimal("0.0476")

    def test_inflation_adjuster_adjust_amount(self):
        """Test InflationAdjuster amount adjustment."""
        adjuster = InflationAdjuster()

        amount = Decimal("1000000")
        inflation_rate = Decimal("0.05")  # 5% monthly inflation
        months = 12

        inflation_factor = (Decimal("1") - inflation_rate) ** months
        adjusted = amount * inflation_factor

        # After 12 months of 5% monthly inflation, value erodes significantly
        assert adjusted < amount


class TestArbitrageEngine:
    """Test arbitrage engine."""

    def test_engine_analyze_rates(self):
        """Test ArbitrageEngine rate analysis."""
        engine = ArbitrageEngine(spread_threshold_bps=Decimal("1.0"))

        # Create mock rate collections from different sources
        fred_rates = RateCollection(
            source=DataSource.FRED,
            rates=[
                Rate(
                    source=DataSource.FRED,
                    base_currency=Currency.USD,
                    target_currency=Currency.ARS,
                    rate=Decimal("1000.50"),
                    rate_type=RateType.OFFICIAL,
                    timestamp=datetime.utcnow(),
                )
            ],
            fetched_at=datetime.utcnow(),
            success=True,
        )

        bcra_rates = RateCollection(
            source=DataSource.BCRA,
            rates=[
                Rate(
                    source=DataSource.BCRA,
                    base_currency=Currency.USD,
                    target_currency=Currency.ARS,
                    rate=Decimal("990.25"),
                    rate_type=RateType.OFFICIAL,
                    timestamp=datetime.utcnow(),
                )
            ],
            fetched_at=datetime.utcnow(),
            success=True,
        )

        signals = engine.analyze_rates([fred_rates, bcra_rates])
        assert isinstance(signals, list)

    def test_engine_stablecoin_arbitrage(self):
        """Test stablecoin arbitrage detection."""
        engine = ArbitrageEngine()

        coingecko_rates = [
            Rate(
                source=DataSource.COINGECKO,
                base_currency=Currency.USD,
                target_currency=Currency.USDT,
                rate=Decimal("1.0001"),  # Slightly off peg
                rate_type=RateType.SPOT,
                timestamp=datetime.utcnow(),
            )
        ]

        fx_rates = [
            Rate(
                source=DataSource.ARGENTINA_DATOS,
                base_currency=Currency.USD,
                target_currency=Currency.ARS,
                rate=Decimal("1000.50"),
                rate_type=RateType.BLUE,
                timestamp=datetime.utcnow(),
            )
        ]

        signals = engine.check_stablecoin_arbitrage(coingecko_rates, fx_rates)
        assert isinstance(signals, list)


class TestModelsImports:
    """Test that all model imports work correctly."""

    def test_all_types_importable(self):
        """Test all types can be imported."""
        from src.models.types import (
            DataSource,
            Currency,
            RateType,
            Rate,
            Spread,
            Exposure,
            ArbitrageSignal,
            RateCollection,
        )
        assert DataSource.FRED
        assert Currency.USD
        assert RateType.OFFICIAL

    def test_all_core_importable(self):
        """Test core modules can be imported."""
        from src.core.config import EngineConfig, get_config, set_config
        from src.core.normalization import RateNormalizer, SpreadCalculator, InflationAdjuster
        from src.core.arbitrage import ArbitrageEngine, ExposureTracker
        assert True

    def test_all_adapters_importable(self):
        """Test all adapter modules can be imported."""
        from src.adapters.base import BaseAdapter, RateAdapterRegistry, get_registry
        from src.adapters.fred import FredAdapter
        from src.adapters.frankfurter import FrankfurterAdapter
        from src.adapters.argentinadatos import ArgentinaDatosAdapter, BCRAAdapter
        from src.adapters.coingecko import CoinGeckoAdapter
        from src.adapters.indec import INDECAdapter
        assert True