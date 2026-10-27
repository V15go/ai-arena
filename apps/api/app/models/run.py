from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TextArray


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_version_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_versions.id"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String, nullable=False, default="ARENA")
    status: Mapped[str] = mapped_column(String, nullable=False, default="QUEUED")
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Run-level budget counters; only the orchestrator updates them (conditional UPDATE).
    total_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planner_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    est_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONType)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(["agent_id", "agent_version"], ["agents.id", "agents.version"]),
        UniqueConstraint("run_id", "task_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_key: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    # NULL only for HUMAN_APPROVAL tasks, which no agent executes.
    agent_id: Mapped[str | None] = mapped_column(String)
    agent_version: Mapped[str | None] = mapped_column(String)
    access: Mapped[str] = mapped_column(String, nullable=False, default="READ")
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    depends_on: Mapped[list[str]] = mapped_column(TextArray, nullable=False, default=list)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskAttempt(Base):
    __tablename__ = "task_attempts"
    __table_args__ = (UniqueConstraint("task_id", "attempt_no"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    failure_class: Mapped[str | None] = mapped_column(String)
    fingerprint: Mapped[str | None] = mapped_column(String)
    recovery_decision: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    decision_source: Mapped[str | None] = mapped_column(String)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONType)


class ExecutionEvent(Base):
    __tablename__ = "execution_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq"),
        Index("ix_execution_events_run_id_seq", "run_id", "seq"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
