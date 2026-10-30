from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import get_simulation_engine
from app.core.config import get_settings
from app.domain.scenarios import SimulationScenario
from app.services.simulation_engine import SimulationEngine, SimulationStatus

router = APIRouter(tags=["Simulator Controls"])


class StartSimulationRequest(BaseModel):
    scenario: SimulationScenario = Field(
        default=SimulationScenario.NORMAL_DRIVING,
        description="Automotive operational scenario to simulate",
    )
    vehicles_count: Optional[int] = Field(
        default=None, ge=1, le=5000, description="Total number of simulated vehicles in fleet"
    )
    rate_per_sec: Optional[int] = Field(
        default=None, ge=1, le=5000, description="Target telemetry emission rate in messages per second"
    )
    seed: Optional[int] = Field(
        default=None, description="Deterministic pseudo-random seed for reproducibility"
    )
    duration_seconds: Optional[int] = Field(
        default=None, ge=1, description="Automatic duration limit in seconds (runs indefinitely if omitted)"
    )


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> Dict[str, str]:
    """Liveness probe indicating the simulator process is active."""
    return {"status": "UP", "service": "erp-iot-simulator"}


@router.post("/api/v1/simulator/start", status_code=status.HTTP_202_ACCEPTED)
async def start_simulation(
    req: StartSimulationRequest,
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> Dict[str, Any]:
    """Start an asynchronous telemetry simulation run with configured parameters."""
    settings = get_settings()

    vehicle_count = req.vehicles_count or settings.DEFAULT_VEHICLES
    rate_per_sec = req.rate_per_sec or settings.DEFAULT_RATE_LIMIT
    seed = req.seed if req.seed is not None else settings.DEFAULT_RANDOM_SEED

    await engine.start(
        scenario=req.scenario,
        vehicle_count=vehicle_count,
        rate_per_sec=rate_per_sec,
        seed=seed,
        duration_seconds=req.duration_seconds,
    )

    return {
        "status": "started",
        "scenario": req.scenario.value,
        "vehicles_count": vehicle_count,
        "rate_per_sec": rate_per_sec,
        "seed": seed,
        "duration_seconds": req.duration_seconds,
    }


@router.post("/api/v1/simulator/stop", status_code=status.HTTP_200_OK)
async def stop_simulation(
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> Dict[str, str]:
    """Stop active simulation execution."""
    await engine.stop()
    return {"status": "stopped"}


@router.get("/api/v1/simulator/status", status_code=status.HTTP_200_OK)
async def get_simulation_status(
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> SimulationStatus:
    """Retrieve current operational status, real-time throughput, and message counters."""
    return engine.get_status()
