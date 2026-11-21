"""Health check and status endpoints for the FX Treasury Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from fastapi import APIRouter

from src.core.engine import FXTreasuryEngine
from src.core.config import get_config

logger = structlog.get_logger(__name__)

router = APIRouter()


async def get_engine() -> FXTreasuryEngine:
    """Dependency to get the engine instance."""
    engine = FXTreasuryEngine()
    await engine.initialize()
    return engine


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "data_sources": [s.value for s in get_config().sources.keys()],
    }


@router.get("/health/sources")
async def health_check_sources() -> dict[str, Any]:
    """Check status of all data sources."""
    sources_status: dict[str, bool] = {}
    for name, source in get_config().sources.items():
        sources_status[name] = source.enabled

    return {
        "status": "healthy",
        "sources": sources_status,
        "checked_at": datetime.utcnow().isoformat(),
    }


@router.get("/engine/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check - verify all critical components are operational."""
    ready = True
    details: dict[str, Any] = {}

    # Check config
    config = get_config()
    if not config.sources:
        ready = False
        details["config_error"] = "No data sources configured"

    details["configured_sources"] = len(config.sources)
    details["timestamp"] = datetime.utcnow().isoformat()

    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        **details,
    }
