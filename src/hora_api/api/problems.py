"""RFC 9457 problem details (application/problem+json)."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"


class ProblemError(Exception):
    """Raise from anywhere in a request to produce a problem+json response."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        *,
        type_: str = "about:blank",
        headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(detail or title)
        self.status, self.title, self.detail = status, title, detail
        self.type_, self.headers, self.extra = type_, headers, extra


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: str | None = None,
    *,
    type_: str = "about:blank",
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {"type": type_, "title": title, "status": status}
    if detail:
        body["detail"] = detail
    body["instance"] = request.url.path
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


class ProblemDetail(BaseModel):
    """RFC 9457 problem details body (documented in OpenAPI for error responses)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(
            request, exc.status, exc.title, exc.detail, type_=exc.type_, headers=exc.headers,
            **exc.extra,
        )  # fmt: skip

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = HTTPStatus(exc.status_code).phrase
        detail = exc.detail if exc.detail and exc.detail != title else None
        headers = dict(exc.headers) if exc.headers else None
        return problem_response(request, exc.status_code, title, detail, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return problem_response(
            request, 422, "Invalid request", "One or more parameters are invalid.",
            type_="urn:hora-api:problem:validation", errors=errors,
        )  # fmt: skip

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        return problem_response(request, 500, "Internal Server Error")
