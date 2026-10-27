from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base for every API schema: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class Page(ApiModel, Generic[T]):  # noqa: UP046 - keeps OpenAPI component names stable
    items: list[T]
    next_cursor: str | None = None


class ErrorBody(ApiModel):
    code: str
    message: str
    request_id: str | None = None
    details: object | None = None


class ErrorResponse(ApiModel):
    error: ErrorBody
