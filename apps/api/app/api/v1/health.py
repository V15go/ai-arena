from typing import Literal

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionDep
from app.schemas.common import ApiModel

router = APIRouter(tags=["health"])


class HealthOut(ApiModel):
    status: Literal["ok"]


class ReadyOut(ApiModel):
    status: Literal["ok"]
    database: Literal["ok"]


@router.get("/health", response_model=HealthOut, operation_id="getHealth")
async def health() -> HealthOut:
    """Liveness only: needs no database, Meta API or Modal credentials."""
    return HealthOut(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadyOut,
    operation_id="getReadiness",
    responses={503: {"description": "Database not configured or unreachable"}},
)
async def ready(session: SessionDep) -> ReadyOut:
    await session.execute(text("SELECT 1"))
    return ReadyOut(status="ok", database="ok")
