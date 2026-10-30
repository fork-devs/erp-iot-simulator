from fastapi import HTTPException, Request, status
from app.services.simulation_engine import SimulationEngine


def get_simulation_engine(request: Request) -> SimulationEngine:
    """Dependency providing the SimulationEngine instance from application state."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Simulation engine is unavailable",
        )
    return engine
