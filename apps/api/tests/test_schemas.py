import pytest
from pydantic import ValidationError

from app.schemas.enums import TaskType
from app.schemas.sandbox import ExecRequest, SandboxSpec
from app.schemas.workflows import MAX_TASKS, WorkflowDefinition, WorkflowPolicy, WorkflowTaskDef


def task(i: int, **kw: object) -> dict[str, object]:
    return {"id": f"t{i}", "type": "FIX", "agentId": "fix", "title": "x", **kw}


def definition(tasks: list[dict[str, object]]) -> dict[str, object]:
    return {
        "name": "n",
        "goal": "g",
        "repositoryId": "r",
        "acceptanceCriteria": ["ok"],
        "tasks": tasks,
    }


def test_definition_uses_camel_case_and_round_trips() -> None:
    d = WorkflowDefinition.model_validate(definition([task(1)]))
    assert d.repository_id == "r"
    dumped = d.model_dump(by_alias=True)
    assert "repositoryId" in dumped
    assert dumped["tasks"][0]["agentId"] == "fix"


def test_task_limit_is_enforced() -> None:
    WorkflowDefinition.model_validate(definition([task(i) for i in range(MAX_TASKS)]))
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate(definition([task(i) for i in range(MAX_TASKS + 1)]))


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowTaskDef.model_validate(task(1, **{"shell": "rm -rf /"}))


def test_agent_required_except_for_approval_tasks() -> None:
    with pytest.raises(ValidationError, match="agentId"):
        WorkflowTaskDef.model_validate({"id": "a", "type": "FIX", "title": "x"})
    ok = WorkflowTaskDef.model_validate({"id": "a", "type": "HUMAN_APPROVAL", "title": "x"})
    assert ok.type is TaskType.HUMAN_APPROVAL and ok.agent_id is None


def test_policy_defaults_and_bounds() -> None:
    assert WorkflowPolicy().max_concurrency == 3
    with pytest.raises(ValidationError):
        WorkflowPolicy(max_concurrency=0)


def test_exec_request_is_structured_argv_only() -> None:
    with pytest.raises(ValidationError):
        ExecRequest(argv=[])
    with pytest.raises(ValidationError):
        ExecRequest.model_validate({"argv": "pytest -q"})  # a shell string is not accepted


def test_sandbox_spec_cannot_request_env() -> None:
    assert "env" not in SandboxSpec.model_fields
