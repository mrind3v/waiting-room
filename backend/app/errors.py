from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Domain error rendered as {"detail": str, "code": str}."""

    def __init__(self, status_code: int, code: str, detail: str, **extra):
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.extra = extra


def _payload(code: str, detail: str, **extra) -> dict:
    return {"detail": detail, "code": code, **extra}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(
            _payload(exc.code, exc.detail, **exc.extra), status_code=exc.status_code
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            _payload(f"HTTP_{exc.status_code}", str(exc.detail)), status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        msgs = [
            f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()
        ]
        return JSONResponse(_payload("VALIDATION_ERROR", "; ".join(msgs)), status_code=422)
