from sqlalchemy import JSON, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase

# JSONB on Postgres (Neon); plain JSON elsewhere so unit tests can run on SQLite.
JSONType = JSON().with_variant(JSONB(), "postgresql")
TextArray = JSON().with_variant(ARRAY(Text()), "postgresql")


class Base(DeclarativeBase):
    pass
