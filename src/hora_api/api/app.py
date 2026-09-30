"""FastAPI application factory. `make run` serves `hora_api.api.app:app`."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response

import hora_api
from hora_api.api.problems import install_handlers
from hora_api.api.profiles import ProfileStore
from hora_api.api.routes import health, router
from hora_api.api.service import DayCache, Services
from hora_api.api.settings import ApiSettings
from hora_api.data.loader import load_scoring_tables, load_tables
from hora_api.scoring.settings import ScoringSettings

log = structlog.get_logger("hora_api")


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    cfg = settings or ApiSettings()
    app = FastAPI(
        title="hora-api",
        version=hora_api.__version__,
        summary="Favourable horas and time windows for a person, date and place",
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
        redoc_url=None,
    )
    app.state.services = Services(
        settings=cfg,
        tables=load_tables(cfg.data_dir),
        scoring_tables=load_scoring_tables(cfg.data_dir),
        scoring=ScoringSettings(),
        profiles=ProfileStore(cfg.profiles_file),
        cache=DayCache(cfg.cache_size),
    )
    install_handlers(app)
    app.include_router(router)
    app.include_router(health)

    @app.middleware("http")
    async def access_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Path only: query strings carry coordinates and profile ids; headers carry API keys.
        start = time.perf_counter()
        response = await call_next(request)
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return response

    return app


app = create_app()
