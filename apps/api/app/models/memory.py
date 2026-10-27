from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType


class WorkflowMemory(Base):
    """Experience memory. ``evidence`` and ``source_attempt_id`` are NOT NULL on purpose:
    the database refuses a lesson that is not backed by a recorded attempt."""

    __tablename__ = "workflow_memories"
    __table_args__ = (
        Index("ix_workflow_memories_workflow_fingerprint", "workflow_id", "fingerprint"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    failure_class: Mapped[str] = mapped_column(String, nullable=False)
    strategy: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    source_attempt_id: Mapped[str] = mapped_column(ForeignKey("task_attempts.id"), nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=0)
    env_constraints: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
