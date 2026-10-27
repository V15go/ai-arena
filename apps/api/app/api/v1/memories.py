from fastapi import APIRouter

from app.api.deps import AuthDep, CursorParam, LimitParam, SessionDep
from app.models import WorkflowMemory
from app.repositories.base import list_page
from app.schemas.common import Page
from app.schemas.memory import MemoryRecordOut

router = APIRouter(prefix="/memories", tags=["memory"])


@router.get("", response_model=Page[MemoryRecordOut], operation_id="listMemories")
async def list_memories(
    _: AuthDep,
    session: SessionDep,
    workflow_id: str | None = None,
    limit: LimitParam = 20,
    cursor: CursorParam = None,
) -> Page[MemoryRecordOut]:
    where = (WorkflowMemory.workflow_id == workflow_id,) if workflow_id else ()
    rows, next_cursor = await list_page(
        session, WorkflowMemory, WorkflowMemory.id, limit=limit, cursor=cursor, where=where
    )
    return Page[MemoryRecordOut](
        items=[MemoryRecordOut.model_validate(r) for r in rows], next_cursor=next_cursor
    )
