"""Domain errors and the handlers that turn them into consistent JSON responses.

Every error the API returns has the same envelope:
    {"error": {"code": "not_found", "message": "...", "details": ...}}
with a matching HTTP status code, so the frontend can branch on `response.ok`.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code, code, message = 400, "bad_request", "The request could not be processed."


class AuthenticationError(AppError):
    status_code, code, message = 401, "not_authenticated", "Authentication required."


class PermissionDeniedError(AppError):
    status_code, code, message = 403, "permission_denied", "You cannot access this resource."


class NotFoundError(AppError):
    status_code, code, message = 404, "not_found", "Resource not found."


class ConflictError(AppError):
    status_code, code, message = 409, "conflict", "Resource already exists."


class LLMServiceError(AppError):
    status_code, code, message = 502, "llm_unavailable", "The language model is unavailable."


class DatabaseUnavailableError(AppError):
    status_code, code, message = 503, "database_unavailable", "The database is unavailable."


def _envelope(status: int, code: str, message: str, details: Any = None, headers=None):
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status, content=body, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return _envelope(exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return _envelope(422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # One summary line only: Starlette re-raises the exception after this handler
        # returns, so the server (uvicorn) prints the full traceback itself.
        logger.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
        return _envelope(500, AppError.code, AppError.message)
