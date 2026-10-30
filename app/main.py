from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.v1.simulator import router as simulator_router
from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.LOG_LEVEL)

app = FastAPI(
    title="DriveOS - ERP IoT Telemetry Simulator",
    description="Ephemeral high-throughput telemetry generator and failure scenario simulator (Dev/Staging Only)",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "prod" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "prod" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(simulator_router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "erp-iot-simulator",
        "environment": settings.ENVIRONMENT,
        "mode": "dev/staging simulation",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.SERVER_PORT, reload=False)
