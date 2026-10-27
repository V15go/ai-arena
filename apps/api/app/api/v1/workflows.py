from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AuthDep, CursorParam, LimitParam, SessionDep
from app.models import Workflow, WorkflowVersion
from app.repositories.base import get_or_404, list_page
from app.schemas.common import ApiModel, Page
from app.schemas.workflows import WorkflowOut, WorkflowVersionOut

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowVersionList(ApiModel):
    items: list[WorkflowVersionOut]


@router.get("", response_model=Page[WorkflowOut], operation_id="listWorkflows")
async def list_workflows(
    _: AuthDep, session: SessionDep, limit: LimitParam = 20, cursor: CursorParam = None
) -> Page[WorkflowOut]:
    rows, next_cursor = await list_page(session, Workflow, Workflow.id, limit=limit, cursor=cursor)
    return Page[WorkflowOut](
        items=[WorkflowOut.model_validate(r) for r in rows], next_cursor=next_cursor
    )


@router.get("/{workflow_id}", response_model=WorkflowOut, operation_id="getWorkflow")
async def get_workflow(workflow_id: str, _: AuthDep, session: SessionDep) -> WorkflowOut:
    row = await get_or_404(session, Workflow, workflow_id, "Workflow")
    return WorkflowOut.model_validate(row)


@router.get(
    "/{workflow_id}/versions",
    response_model=WorkflowVersionList,
    operation_id="listWorkflowVersions",
)
async def list_versions(workflow_id: str, _: AuthDep, session: SessionDep) -> WorkflowVersionList:
    await get_or_404(session, Workflow, workflow_id, "Workflow")
    rows = (
        await session.scalars(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version.desc())
        )
    ).all()
    return WorkflowVersionList(items=[WorkflowVersionOut.model_validate(r) for r in rows])
