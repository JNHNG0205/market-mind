"""Error envelope: `{"error": {"code", "message", "trace_id"}}` for every non-2xx API response."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from marketmind.core.context import current_trace_id
from marketmind.core.errors import AppError


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "trace_id": current_trace_id()}},
    )


async def _app_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.http_status, exc.code, exc.message)


async def _validation_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    first = exc.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return error_response(400, "validation_error", f"{where}: {first['msg']}")


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


async def _http_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    response = error_response(
        exc.status_code, _HTTP_CODES.get(exc.status_code, "http_error"), str(exc.detail)
    )
    if exc.headers:
        response.headers.update(exc.headers)
    return response


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
