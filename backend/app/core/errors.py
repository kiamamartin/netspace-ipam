"""Consistent error structure and exception handlers.

Error payload shape (used for every error response):

    {"error": {"code": "invalid_cidr", "message": "...", "details": [...]}}

Stack traces, credentials and internal details are never exposed.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Application-level error carrying a machine-readable code and HTTP status."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []

    def to_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


# Convenience constructors -------------------------------------------------

def validation_error(message: str, details: list[dict[str, Any]] | None = None) -> AppError:
    return AppError("validation_error", message, 422, details)


def unprocessable(message: str, details: list[dict[str, Any]] | None = None) -> AppError:
    return AppError("validation_error", message, 422, details)


def not_found(resource: str, ident: Any) -> AppError:
    return AppError("not_found", f"{resource} with id '{ident}' was not found", 404)


def conflict(code: str, message: str, details: list[dict[str, Any]] | None = None) -> AppError:
    return AppError(code, message, 409, details)


# Handlers -----------------------------------------------------------------

def _error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or []}}


def register_exception_handlers(app: FastAPI) -> None:
    # Domain errors raised by the service layer as bare ``ValueError("code")``
    # are translated here to consistent HTTP statuses with the same envelope.
    # Codes map to the service module's documented taxonomy:
    #   404 not found · 409 conflicts · 422 validation failures.
    # Any unrecognized ValueError still falls through to the internal-error
    # handler (500) so genuine bugs are never misclassifed as client errors.
    _DOMAIN_ERROR_STATUS: dict[str, int] = {
        "not_found": 404,
        "duplicate_name": 409,
        "duplicate_cidr": 409,
        "overlap": 409,
        "network_not_empty": 409,
        "subnet_not_empty": 409,
        "duplicate_assignment": 409,
        "ip_assigned": 409,
        "plan_archived": 409,
        "plan_active": 409,
        "plan_empty": 409,
        "insufficient_capacity": 409,
        "insufficient_space": 409,
        "not_enough_subnets": 409,
        "invalid_cidr": 422,
        "invalid_address": 422,
        "misaligned_prefix": 422,
        "cidr_outside_parent": 422,
        "address_outside_subnet": 422,
        "reserved_address": 422,
        "gateway_out_of_range": 422,
        "gateway_reserved": 422,
        "vlsm_error": 422,
    }

    @app.exception_handler(ValueError)
    async def _domain_value_error(request: Request, exc: ValueError) -> JSONResponse:
        code = str(exc)
        status_code = _DOMAIN_ERROR_STATUS.get(code)
        if status_code is None:
            # Not a recognizable domain error — keep it as an internal failure.
            return JSONResponse(
                status_code=500,
                content=_error_payload("internal_error", "An unexpected internal error occurred"),
            )
        message = code.replace("_", " ")
        return JSONResponse(status_code=status_code, content=_error_payload(code, message))

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ())),
                "message": err.get("msg", "invalid value"),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "validation_error", "Request validation failed", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            400: "bad_request",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            413: "payload_too_large",
        }.get(exc.status_code, "http_error")
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(code, detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never expose stack traces or internal details.
        return JSONResponse(
            status_code=500,
            content=_error_payload("internal_error", "An unexpected internal error occurred"),
        )
