from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_simulation_engine
from app.core.config import get_settings
from app.core.metrics import get_metrics_content, get_metrics_content_type
from app.domain.scenarios import SimulationScenario
from app.services.simulation_engine import SimulationEngine, SimulationStatus

router = APIRouter(tags=["Simulator Controls"])


class StartSimulationRequest(BaseModel):
    scenario: SimulationScenario = Field(
        default=SimulationScenario.NORMAL_DRIVING,
        description="Automotive operational scenario to simulate",
    )
    emission_mode: Optional[str] = Field(
        default=None,
        pattern="^(STREAM|BATCH|stream|batch)$",
        description="Telemetry emission mode: STREAM (/api/v1/iot/telemetry) or BATCH (/api/v1/telemetry-batches)",
    )
    branch_id: Optional[str] = Field(
        default=None,
        description="Target branch UUID for fleet attribution",
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


class BurstSimulationRequest(BaseModel):
    scenario: SimulationScenario = Field(
        default=SimulationScenario.HIGH_THROUGHPUT_BURST,
        description="Automotive operational scenario for burst emission",
    )
    batch_size: int = Field(
        default=50, ge=1, le=100, description="Number of snapshots/packets in burst (1-100)"
    )
    emission_mode: str = Field(
        default="BATCH",
        pattern="^(STREAM|BATCH|stream|batch)$",
        description="Emission mode: STREAM or BATCH",
    )
    branch_id: Optional[str] = Field(
        default=None,
        description="Target branch UUID for fleet attribution",
    )
    device_id: Optional[str] = Field(
        default=None,
        description="Target OBD2 device ID",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Deterministic pseudo-random seed",
    )


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> Dict[str, str]:
    """Liveness probe indicating the simulator process is active."""
    return {"status": "UP", "service": "erp-iot-simulator"}


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def metrics() -> Response:
    """Expose real-time Prometheus operational metrics for scraping."""
    return Response(
        content=get_metrics_content(),
        media_type=get_metrics_content_type(),
    )


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
    emission_mode = req.emission_mode or settings.EMISSION_MODE
    branch_id = req.branch_id or settings.DEFAULT_BRANCH_ID

    await engine.start(
        scenario=req.scenario,
        vehicle_count=vehicle_count,
        rate_per_sec=rate_per_sec,
        seed=seed,
        duration_seconds=req.duration_seconds,
        emission_mode=emission_mode,
        branch_id=branch_id,
    )

    return {
        "status": "started",
        "scenario": req.scenario.value,
        "emission_mode": emission_mode.upper(),
        "branch_id": branch_id,
        "vehicles_count": vehicle_count,
        "rate_per_sec": rate_per_sec,
        "seed": seed,
        "duration_seconds": req.duration_seconds,
    }


@router.post("/api/v1/simulator/burst", status_code=status.HTTP_200_OK)
async def trigger_burst(
    req: BurstSimulationRequest,
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> Dict[str, Any]:
    """Trigger an immediate synchronous one-shot burst emission."""
    settings = get_settings()
    seed = req.seed if req.seed is not None else settings.DEFAULT_RANDOM_SEED

    result = await engine.send_burst(
        batch_size=req.batch_size,
        scenario=req.scenario,
        emission_mode=req.emission_mode,
        branch_id=req.branch_id,
        device_id=req.device_id,
        seed=seed,
    )
    return result


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
