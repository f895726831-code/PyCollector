"""FastAPI error handling framework.

Provides a generic ``AppError`` exception with enum-based error codes
and pre-built FastAPI exception handlers that produce consistent JSON
error responses.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from pycollector.domain.enums import ErrorCode


class ErrorResponse(BaseModel):
    """Standard JSON error response body."""

    model_config = ConfigDict(use_enum_values=True)

    error_code: ErrorCode
    error_message: str


class AppError(Exception):
    """Application-level exception with structured detail.

    Parameters
    ----------
    error_code:
        Machine-readable error code from :class:`ErrorCode`.
    error_message:
        Human-readable error description.
    status_code:
        HTTP status code for the response.
    detail:
        Optional structured detail dictionary (e.g. execution steps,
        warnings, skipped items).
    """

    def __init__(
        self,
        error_code: ErrorCode,
        error_message: str,
        status_code: int,
        detail: dict | None = None,
    ) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message
        self.status_code = status_code
        self.detail = detail or {}


def register_exception_handlers(app: FastAPI) -> None:
    """Register standard exception handlers on a FastAPI application.

    Handles:
    - :class:`AppError` → structured JSON with the error's status code.
    - :class:`ValueError` → 400 with ``INVALID_QUERY_PARAM``.
    - :class:`RequestValidationError` → 400 with ``INVALID_QUERY_PARAM``.
    - Unhandled :class:`Exception` → 500 with ``INTERNAL_ERROR``.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=exc.error_code,
                error_message=exc.error_message,
            ).model_dump(),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error_code=ErrorCode.INVALID_QUERY_PARAM,
                error_message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        message = "; ".join(error["msg"] for error in exc.errors())
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error_code=ErrorCode.INVALID_QUERY_PARAM,
                error_message=message,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code=ErrorCode.INTERNAL_ERROR,
                error_message=str(exc) or "internal server error",
            ).model_dump(),
        )