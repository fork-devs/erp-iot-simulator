from contextlib import asynccontextmanager
import logging
import sys
from typing import AsyncGenerator
from fastapi import FastAPI

from app.core.config import get_settings
from app.services.http_emitter import HttpEmitter
from app.services.simulation_engine import SimulationEngine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI application lifespan manager with production environment guardrail."""
    settings = get_settings()

    # 1. Production Execution Guardrail (QA-4 / QA-5 / Architecture rule)
    if settings.ENVIRONMENT.lower() in ["prod", "production"]:
        logger.critical(
            "FATAL: erp-iot-simulator is an ephemeral development tool and is STRICTLY PROHIBITED in production!"
        )
        sys.exit(1)

    logger.info(f"Starting erp-iot-simulator in {settings.ENVIRONMENT} mode on port {settings.SERVER_PORT}...")

    # 2. Initialize HTTP Emitter and Simulation Engine
    emitter = HttpEmitter(
        ingestion_url=settings.INGESTION_URL,
        device_key=settings.DEVICE_KEY,
        timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
        max_connections=settings.HTTP_POOL_CONNECTIONS,
    )
    engine = SimulationEngine(
        emitter=emitter,
        tenant_id=settings.TENANT_ID,
    )

    app.state.emitter = emitter
    app.state.engine = engine

    yield

    # 3. Graceful Shutdown
    logger.info("Shutting down erp-iot-simulator...")
    if engine.is_running:
        await engine.stop()
    await emitter.close()
    logger.info("erp-iot-simulator shutdown complete")
