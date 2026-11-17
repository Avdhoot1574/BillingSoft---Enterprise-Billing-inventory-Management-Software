"""Structured API errors with stable machine-readable codes."""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger("app.errors")

# Prefixes raised by database triggers/functions (see alembic/sql/0002_v2_fixes.sql).
DB_ERROR_CODES = (
    "INSUFFICIENT_STOCK",
    "JOURNAL_NOT_BALANCED",
    "JOURNAL_IMMUTABLE",
    "RECORD_IMMUTABLE",
    "PAYMENT_OVER_ALLOCATED",
    "DOCUMENT_OVER_ALLOCATED",
    "ALLOCATION_DIRECTION_MISMATCH",
)


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def _body(request: Request, code: str, message: str, details: Any | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.message, exc.details),
                            status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
                   for e in exc.errors()]
        return JSONResponse(_body(request, "VALIDATION_ERROR", "Request validation failed", details),
                            status_code=422)

    @app.exception_handler(DBAPIError)
    async def _db_error(request: Request, exc: DBAPIError):
        text = str(getattr(exc, "orig", exc))
        for code in DB_ERROR_CODES:
            if code + ":" in text:
                message = text.split(code + ":", 1)[1].strip().splitlines()[0]
                return JSONResponse(_body(request, code, message), status_code=409)
        logger.exception("Unhandled database error", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(_body(request, "INTERNAL_ERROR", "Unexpected error"), status_code=500)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(_body(request, "INTERNAL_ERROR", "Unexpected error"), status_code=500)
