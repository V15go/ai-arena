"""Read-only repository helpers. Writes to run/task state go through the Orchestrator only."""

from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import NotFoundError

MAX_LIMIT = 100


async def list_page[M](
    session: AsyncSession,
    model: type[M],
    id_column: InstrumentedAttribute[str],
    *,
    limit: int,
    cursor: str | None,
    where: tuple[ColumnElement[bool], ...] = (),
) -> tuple[list[M], str | None]:
    """Newest-first keyset pagination on a time-sortable (ULID) id."""
    limit = max(1, min(limit, MAX_LIMIT))
    stmt = select(model).where(*where).order_by(id_column.desc()).limit(limit + 1)
    if cursor:
        stmt = stmt.where(id_column < cursor)
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = getattr(rows[-1], id_column.key) if has_more else None
    return rows, next_cursor


async def get_or_404[M](session: AsyncSession, model: type[M], pk: Any, what: str) -> M:
    row = await session.get(model, pk)
    if row is None:
        raise NotFoundError(what)
    return row
