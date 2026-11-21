"""FastAPI application for the FX Treasury Engine."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI

from src.api.health import router as health_router
from src.core.config import get_config
from src.core.engine import FXTreasuryEngine


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Cross-Border FX & Treasury Risk Engine",
        description="Multi-currency treasury pipeline for global FX exposure management",
        version="0.1.0",
    )

    app.include_router(health_router, prefix="/api/v1")

    @app.get("/api/v1/engine/status")
    async def engine_status() -> dict[str, Any]:
        """Get engine status."""
        engine = FXTreasuryEngine()
        status = await engine.run_analysis()
        return status

    @app.get("/api/v1/rates/{source}")
    async def get_rates(source: str) -> dict[str, Any]:
        """Get rates from a specific source."""
        from src.models.types import DataSource

        try:
            data_source = DataSource(source.upper())
            engine = FXTreasuryEngine()
            # Fetch from specific source via registry
            adapter = engine.registry.get(data_source)
            if not adapter:
                return {
                    "error": f"Source {source} not found",
                    "status": "error",
                }
            rates = await adapter.fetch_rates()
            return {
                "source": source,
                "success": len(rates.rates) > 0,
                "rates": [r.model_dump() for r in rates.rates],
                "fetched_at": rates.fetched_at.isoformat(),
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "error",
            }

    @app.get("/api/v1/analyze")
    async def run_full_analysis() -> dict[str, Any]:
        """Run the full arbitrage and exposure analysis."""
        engine = FXTreasuryEngine()
        results = await engine.run_analysis()
        return results

    @app.post("/api/v1/exposure")
    async def add_exposure(
        currency: str,
        amount: float,
        exchange_rate: float,
        inflation_rate: float = 0.0,
    ) -> dict[str, Any]:
        """Add a treasury exposure position."""
        from src.models.types import Currency

        currency_enum = Currency(currency)
        engine = FXTreasuryEngine()
        exposure = await engine.add_position(
            currency_enum,
            Decimal(str(amount)),
            Decimal(str(exchange_rate)),
            Decimal(str(inflation_rate)),
        )
        return {
            "status": "success",
            "exposure": exposure.model_dump(),
        }

    return app


_engine_instance = None


def get_engine_instance() -> FastAPI:
    """Get or create FastAPI instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = create_app()
    return _engine_instance
