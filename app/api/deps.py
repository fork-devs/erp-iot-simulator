from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.security import (
    SIMULATOR_ADMIN_ROLES,
    SIMULATOR_READ_ROLES,
    extract_roles,
    verify_access_token,
)
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


def get_authenticated_claims(
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Validate Bearer JWT token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization Bearer token",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization Bearer token",
        )
    return verify_access_token(token)


def require_simulator_admin(
    claims: dict[str, Any] = Depends(get_authenticated_claims),
) -> dict[str, Any]:
    """Ensure caller holds an administrative role to control simulations."""
    roles = extract_roles(claims)
    if not (roles & SIMULATOR_ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to control IoT simulator",
        )
    return claims


def require_simulator_reader(
    claims: dict[str, Any] = Depends(get_authenticated_claims),
) -> dict[str, Any]:
    """Ensure caller holds an authorized role to inspect simulator status."""
    roles = extract_roles(claims)
    if not (roles & SIMULATOR_READ_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to read IoT simulator status",
        )
    return claims
