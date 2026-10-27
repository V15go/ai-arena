from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.errors import DatabaseNotConfiguredError

SessionFactory = async_sessionmaker[AsyncSession]


def create_engine(settings: Settings) -> AsyncEngine:
    if not settings.database_url:
        raise DatabaseNotConfiguredError
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if settings.database_url.startswith("postgresql"):
        # Neon's pooled endpoint runs PgBouncer in transaction mode: no prepared-statement cache.
        kwargs["connect_args"] = {"statement_cache_size": 0}
    return create_async_engine(settings.database_url, **kwargs)


def get_session_factory(request: Request) -> SessionFactory:
    """Engine is created lazily so the app (and /health) start without a database."""
    state = request.app.state
    if getattr(state, "session_factory", None) is None:
        engine = create_engine(state.settings)
        state.engine = engine
        state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    factory: SessionFactory = state.session_factory
    return factory


async def get_session(
    factory: Annotated[SessionFactory, Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
