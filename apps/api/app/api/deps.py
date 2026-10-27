from typing import Annotated

from fastapi import Query

from app.core.security import AuthDep
from app.db.session import SessionDep

LimitParam = Annotated[int, Query(ge=1, le=100)]
CursorParam = Annotated[str | None, Query(max_length=64)]

__all__ = ["AuthDep", "CursorParam", "LimitParam", "SessionDep"]
