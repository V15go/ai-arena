from fastapi import APIRouter

from app.api.deps import AuthDep, CursorParam, LimitParam, SessionDep
from app.models import Approval
from app.repositories.base import list_page
from app.schemas.approvals import ApprovalOut
from app.schemas.common import Page
from app.schemas.enums import ApprovalStatus

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=Page[ApprovalOut], operation_id="listApprovals")
async def list_approvals(
    _: AuthDep,
    session: SessionDep,
    status: ApprovalStatus | None = None,
    limit: LimitParam = 20,
    cursor: CursorParam = None,
) -> Page[ApprovalOut]:
    where = (Approval.status == status.value,) if status else ()
    rows, next_cursor = await list_page(
        session, Approval, Approval.id, limit=limit, cursor=cursor, where=where
    )
    return Page[ApprovalOut](
        items=[ApprovalOut.model_validate(r) for r in rows], next_cursor=next_cursor
    )
