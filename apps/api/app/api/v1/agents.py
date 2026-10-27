from fastapi import APIRouter

from app.api.deps import AuthDep, CursorParam, LimitParam, SessionDep
from app.models import Agent
from app.repositories.base import list_page
from app.schemas.agents import AgentOut
from app.schemas.common import Page

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=Page[AgentOut], operation_id="listAgents")
async def list_agents(
    _: AuthDep, session: SessionDep, limit: LimitParam = 20, cursor: CursorParam = None
) -> Page[AgentOut]:
    rows, next_cursor = await list_page(session, Agent, Agent.id, limit=limit, cursor=cursor)
    return Page[AgentOut](items=[AgentOut.model_validate(r) for r in rows], next_cursor=next_cursor)
