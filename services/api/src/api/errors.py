"""Error envelope and exception handlers (API_CONTRACTS.md "Error shape").

{"error": {"code", "message", "details", "request_id"}}
"""
from __future__ import annotations

import logging

from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Raise this from any router/dependency; main.py registers the handler
    that turns it into the standard envelope."""

    def __init__(self, code: str, http_status: int, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message
        self.details = details or {}


def validation_failed(message: str, details: dict | None = None) -> ApiError:
    return ApiError("VALIDATION_FAILED", 400, message, details)


def unauthenticated(message: str = "Missing or invalid credential") -> ApiError:
    return ApiError("UNAUTHENTICATED", 401, message)


def forbidden(message: str = "Not permitted") -> ApiError:
    return ApiError("FORBIDDEN", 403, message)


def not_found(message: str = "Resource not found") -> ApiError:
    return ApiError("NOT_FOUND", 404, message)


def conflict(message: str, details: dict | None = None) -> ApiError:
    return ApiError("CONFLICT", 409, message, details)


def payload_too_large(message: str = "Payload exceeds the allowed size") -> ApiError:
    return ApiError("PAYLOAD_TOO_LARGE", 413, message)


def rate_limited(retry_after_seconds: int) -> ApiError:
    return ApiError(
        "RATE_LIMITED", 429, "Too many requests", details={"retry_after_seconds": retry_after_seconds}
    )


def internal(message: str = "Internal error") -> ApiError:
    return ApiError("INTERNAL", 500, message)


def _envelope(request: Request, error: ApiError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or "unknown"
    headers = {}
    if error.code == "RATE_LIMITED" and "retry_after_seconds" in error.details:
        headers["Retry-After"] = str(error.details["retry_after_seconds"])
    return JSONResponse(
        status_code=error.http_status,
        headers=headers,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "request_id": request_id,
            }
        },
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return _envelope(request, exc)


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's own 422 body is not the documented envelope, so request
    validation reports VALIDATION_FAILED like every other bad input."""
    return _envelope(
        request, validation_failed("Request body or parameters failed validation",
                                   {"errors": exc.errors()}),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # The message stays generic: exception text carries SQL, table names and
    # occasionally values. The request_id ties the response to this log line.
    request_id = getattr(request.state, "request_id", None) or "unknown"
    log.exception("unhandled error on %s %s (request_id=%s)", request.method, request.url.path, request_id)
    return _envelope(request, internal())
