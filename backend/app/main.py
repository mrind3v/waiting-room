from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from . import metrics  # noqa: F401  (registers custom counters)
from .config import get_settings
from .db import engine
from .errors import install_error_handlers
from .routers import appointments, dashboard, doctors, ops, patients


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Waiting Room API", version=settings.git_sha, lifespan=lifespan)
    install_error_handlers(app)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type"],
        )
    for module in (ops, doctors, patients, appointments, dashboard):
        app.include_router(module.router)
    Instrumentator(excluded_handlers=["/metrics", "/health", "/ready"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    return app


app = create_app()
