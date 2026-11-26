"""Error envelope shared by every API answer: {"error": {"code", "message"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.spa import spa_response

log = logging.getLogger(__name__)

HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
}


class AppError(Exception):
    """An error the API reports to the client with a stable machine-readable code."""

    def __init__(
        self, status: int, code: str, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}


def error_body(code: str, message: str, **extra: object) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    headers = dict(exc.headers)
    if exc.status == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status, headers=headers)


async def _http_error(request: Request, exc: StarletteHTTPException):
    spa_dir = getattr(request.app.state, "spa_dir", None)
    if exc.status_code == 404 and spa_dir is not None:
        page = spa_response(request, spa_dir)
        if page is not None:
            return page
    code = HTTP_CODES.get(exc.status_code, "http_error")
    return JSONResponse(
        error_body(code, str(exc.detail)), status_code=exc.status_code, headers=exc.headers
    )


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"loc": [str(part) for part in err["loc"]], "message": err["msg"]} for err in exc.errors()
    ]
    return JSONResponse(
        error_body("validation_error", "Invalid request", details=details), status_code=422
    )


class UnhandledErrorMiddleware:
    """Answers an unhandled exception with the 500 envelope and logs it once.

    Starlette's own handler for `Exception` runs outside every other middleware (so the response
    would lack the security headers) and re-raises (so the server logs the traceback twice).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if started:  # too late for another answer: let the server close the connection
                raise
            # The traceback goes to the log; the client only learns that something failed.
            log.error("Unhandled error on %s %s", scope["method"], scope["path"], exc_info=exc)
            response = JSONResponse(
                error_body("internal_error", "Internal server error"), status_code=500
            )
            await response(scope, receive, send)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
