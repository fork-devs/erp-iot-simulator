from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import get_settings

NIL_UUID = UUID("00000000-0000-0000-0000-000000000000")
SIMULATOR_ADMIN_ROLES = {"SUPERADMIN", "WORKSHOP_ADMIN", "ADMIN_TALLER"}
SIMULATOR_READ_ROLES = SIMULATOR_ADMIN_ROLES | {"SERVICE_ADVISOR", "ASESOR"}


@lru_cache(maxsize=4)
def get_jwk_client(jwks_url: str) -> PyJWKClient:
    """Cached PyJWKClient instance keyed by JWKS URL."""
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=300)


def parse_non_nil_uuid(raw_value: Any, detail_on_error: str) -> UUID:
    """Parse a UUID and reject the nil UUID (00000000-0000-0000-0000-000000000000)."""
    if raw_value is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail_on_error)
    try:
        parsed = UUID(str(raw_value).strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail_on_error) from exc
    if parsed == NIL_UUID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nil tenant UUID is not permitted",
        )
    return parsed


def extract_roles(payload: dict[str, Any]) -> set[str]:
    """Extract normalized role names from JWT claims."""
    roles: set[str] = set()
    raw_roles = payload.get("roles")
    if isinstance(raw_roles, list):
        roles.update(str(r).upper().removeprefix("ROLE_") for r in raw_roles if r)
    elif isinstance(raw_roles, str) and raw_roles.strip():
        roles.add(raw_roles.strip().upper().removeprefix("ROLE_"))

    single_role = payload.get("role")
    if isinstance(single_role, str) and single_role.strip():
        roles.add(single_role.strip().upper().removeprefix("ROLE_"))
    return roles


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify RS256 JWT signature and claims against JWKS and return validated claims."""
    settings = get_settings()
    try:
        jwk_client = get_jwk_client(settings.JWKS_URL)
        signing_key = jwk_client.get_signing_key_from_jwt(token)

        decode_kwargs: dict[str, Any] = {
            "algorithms": ["RS256"],
            "options": {
                "require": ["exp", "sub", "tenant_id"],
                "verify_signature": True,
                "verify_exp": True,
            },
        }
        if settings.JWT_ISSUER:
            decode_kwargs["issuer"] = settings.JWT_ISSUER

        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify authentication token",
        ) from exc

    token_type = payload.get("type")
    if token_type is not None and token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for API access",
        )

    parse_non_nil_uuid(payload.get("tenant_id"), "Token missing valid tenant_id claim")
    return payload
