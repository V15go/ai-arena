"""Static bearer-token auth. Identity comes from the server, never from the request body."""

import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False, description="Static API token (API_AUTH_TOKEN)")


@dataclass(frozen=True)
class Principal:
    id: str


def require_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    token = request.app.state.settings.api_auth_token
    if token is None:  # fail closed: an unconfigured server never accepts anyone
        raise HTTPException(503, "API authentication is not configured")
    supplied = credentials.credentials if credentials else ""
    if not secrets.compare_digest(supplied.encode(), token.get_secret_value().encode()):
        raise HTTPException(
            401, "Invalid or missing bearer token", headers={"WWW-Authenticate": "Bearer"}
        )
    return Principal(id="admin")


AuthDep = Annotated[Principal, Depends(require_auth)]
