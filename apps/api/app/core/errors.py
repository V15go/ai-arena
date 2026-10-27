"""One error envelope for every failure: ``{"error": {code, message, requestId, details}}``."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("app.errors")

_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


class NotFoundError(AppError):
    def __init__(self, what: str) -> None:
        super().__init__(404, "NOT_FOUND", f"{what} not found")


class ConflictError(AppError):
    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(409, "CONFLICT", message, details)


class DatabaseNotConfiguredError(AppError):
    def __init__(self) -> None:
        super().__init__(503, "DATABASE_NOT_CONFIGURED", "DATABASE_URL is not configured")


def _envelope(
    request: Request, status: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "requestId": getattr(request.state, "request_id", None),
    }
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope(request, exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, "ERROR")
        response = _envelope(request, exc.status_code, code, str(exc.detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return _envelope(request, 422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled exception", exc_info=exc)
        return _envelope(request, 500, "INTERNAL_ERROR", "An unexpected error occurred")
