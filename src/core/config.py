"""Configuration management for the FX Treasury Engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class DataSourceConfig:
    """Configuration for a single data source."""

    name: str
    enabled: bool = True
    cache_ttl_seconds: int = 300
    rate_limit_per_minute: int = 60
    api_key: Optional[str] = None
    base_url: str = ""
    timeout_seconds: int = 30
    retries: int = 3


@dataclass
class EngineConfig:
    """Top-level configuration for the treasury engine."""

    environment: str = "development"
    log_level: str = "INFO"
    cache_backend: str = "memory"
    cache_redis_url: Optional[str] = None
    decimal_precision: int = 8
    spread_threshold_bps: Decimal = field(default_factory=lambda: Decimal("50"))
    data_dir: str = "data"
    sources: dict[str, DataSourceConfig] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "EngineConfig":
        """Load configuration from environment variables."""
        config = cls(
            environment=os.getenv("FX_ENGINE_ENV", "development"),
            log_level=os.getenv("FX_ENGINE_LOG_LEVEL", "INFO"),
            cache_backend=os.getenv("FX_ENGINE_CACHE_BACKEND", "memory"),
            cache_redis_url=os.getenv("FX_ENGINE_REDIS_URL"),
            decimal_precision=int(os.getenv("FX_ENGINE_DECIMAL_PRECISION", "8")),
            spread_threshold_bps=Decimal(
                os.getenv("FX_ENGINE_SPREAD_THRESHOLD_BPS", "50")
            ),
            data_dir=os.getenv("FX_ENGINE_DATA_DIR", "data"),
        )

        config.sources = {
            "FRED": DataSourceConfig(
                name="FRED",
                api_key=os.getenv("FRED_API_KEY"),
                base_url="https://api.stlouisfed.org/fred",
                cache_ttl_seconds=3600,
            ),
            "FRANKFURTER": DataSourceConfig(
                name="FRANKFURTER",
                base_url="https://api.frankfurter.app",
                cache_ttl_seconds=1800,
            ),
            "ARGENTINA_DATOS": DataSourceConfig(
                name="ARGENTINA_DATOS",
                base_url="https://api.argentinadatos.com/v1",
                cache_ttl_seconds=600,
            ),
            "BCRA": DataSourceConfig(
                name="BCRA",
                api_key=os.getenv("BCRA_API_KEY"),
                base_url="https://apis.bcra.gob.ar",
                cache_ttl_seconds=900,
            ),
            "COINGECKO": DataSourceConfig(
                name="COINGECKO",
                base_url="https://api.coingecko.com/api/v3",
                cache_ttl_seconds=60,
            ),
            "INDEC": DataSourceConfig(
                name="INDEC",
                base_url="https://apis.datos.gob.ar/series/api",
                cache_ttl_seconds=86400,
            ),
        }

        return config

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EngineConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        config = cls(
            environment=data.get("environment", "development"),
            log_level=data.get("log_level", "INFO"),
            cache_backend=data.get("cache_backend", "memory"),
            cache_redis_url=data.get("cache_redis_url"),
            decimal_precision=data.get("decimal_precision", 8),
            spread_threshold_bps=Decimal(str(data.get("spread_threshold_bps", 50))),
            data_dir=data.get("data_dir", "data"),
        )
        for source_name, source_data in data.get("sources", {}).items():
            config.sources[source_name] = DataSourceConfig(
                name=source_name,
                enabled=source_data.get("enabled", True),
                cache_ttl_seconds=source_data.get("cache_ttl_seconds", 300),
                api_key=source_data.get("api_key"),
                base_url=source_data.get("base_url", ""),
                timeout_seconds=source_data.get("timeout_seconds", 30),
                retries=source_data.get("retries", 3),
            )
        return config

    def to_yaml(self, path: str | Path) -> None:
        """Save configuration to a YAML file."""
        data: dict[str, Any] = {
            "environment": self.environment,
            "log_level": self.log_level,
            "cache_backend": self.cache_backend,
            "decimal_precision": self.decimal_precision,
            "spread_threshold_bps": str(self.spread_threshold_bps),
            "data_dir": self.data_dir,
            "sources": {},
        }
        for name, source in self.sources.items():
            data["sources"][name] = {
                "enabled": source.enabled,
                "cache_ttl_seconds": source.cache_ttl_seconds,
                "api_key": source.api_key,
                "base_url": source.base_url,
                "timeout_seconds": source.timeout_seconds,
                "retries": source.retries,
            }
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


_CONFIG: Optional[EngineConfig] = None


def get_config() -> EngineConfig:
    """Get or create the global engine configuration."""
    global _CONFIG
    if _CONFIG is None:
        config_path = Path("config/engine.yaml")
        if config_path.exists():
            _CONFIG = EngineConfig.from_yaml(config_path)
        else:
            _CONFIG = EngineConfig.from_env()
    return _CONFIG


def set_config(config: EngineConfig) -> None:
    """Override the global configuration (useful for testing)."""
    global _CONFIG
    _CONFIG = config
