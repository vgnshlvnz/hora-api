"""The MCP server: tools over hora-api, served over streamable HTTP."""

from __future__ import annotations

import hmac
import logging
from typing import Any, Literal

import httpx
import uvicorn
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from hora_mcp import __version__
from hora_mcp.client import HoraApi, HoraApiError
from hora_mcp.settings import Settings

Convention = Literal["tamil", "classical"]
Ayanamsa = Literal["lahiri", "kp"]

_COMMON = """
All arguments are optional and default on the API side: date is today in tz; lat, lon and tz
default to the API's configured place; convention is "tamil" (or "classical"); ayanamsa is
"lahiri" (or "kp"). Times are in the requested timezone."""


class BearerAuth:
    """ASGI middleware: require `Authorization: Bearer <token>` on every HTTP request."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app, self._token = app, token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            supplied = ""
            for name, value in scope["headers"]:
                if name == b"authorization":
                    scheme, _, credentials = value.decode("latin-1").partition(" ")
                    if scheme.lower() == "bearer":
                        supplied = credentials.strip()
            if not hmac.compare_digest(supplied.encode(), self._token.encode()):
                response = JSONResponse(
                    {"error": "unauthorized", "detail": "A valid bearer token is required."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _bearer(headers: Any) -> str | None:
    """The token from an `Authorization: Bearer <token>` header, if present."""
    value = (headers or {}).get("authorization", "") if headers is not None else ""
    scheme, _, credentials = value.partition(" ")
    return credentials.strip() or None if scheme.lower() == "bearer" else None


class RequireBearer:
    """ASGI middleware for passthrough: refuse requests that carry no bearer token at all.

    The token itself is checked by hora-api when a tool forwards it, not here.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and _bearer(dict(_lower(scope["headers"]))) is None:
            response = JSONResponse(
                {
                    "error": "unauthorized",
                    "detail": "A bearer token (your hora-api key) is required.",
                },
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _lower(raw: Any) -> list[tuple[str, str]]:
    return [(k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in raw]


def create_server(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> MCPServer:
    """Build the MCP server. `transport` lets tests stand in for the HTTP API."""
    api = HoraApi(settings, transport)

    def caller_key(ctx: Context) -> str | None:
        """Passthrough: the caller's bearer token is the API key; else None (configured key)."""
        if not settings.passthrough:
            return None
        key = _bearer(ctx.headers)
        if key is None:
            raise HoraApiError(
                "no bearer token on the request; passthrough needs your hora-api key"
            )
        return key

    server = MCPServer(
        "hora-api",
        version=__version__,
        instructions=(
            "Favourable horas and time windows for a date and place, from a hora-api server. "
            "Tools return the API's JSON unchanged."
        ),
    )

    @server.tool(
        name="hora_day_card",
        description="Chat card for one day: sun times, Moon transitions, windows to avoid "
        "(Rahu kalam, Yamagandam, Gulika kalam, Durmuhurta, Varjyam), Nalla Neram (Gowri) "
        "and the 24 horas." + _COMMON,
    )
    async def hora_day_card(
        ctx: Context,
        date: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        tz: str | None = None,
        convention: Convention | None = None,
        ayanamsa: Ayanamsa | None = None,
    ) -> dict[str, Any]:
        params = {
            "date": date, "lat": lat, "lon": lon, "tz": tz,
            "convention": convention, "ayanamsa": ayanamsa,
        }  # fmt: skip
        result: dict[str, Any] = await api.get("/v1/cards/day", params, caller_key(ctx))
        return result

    @server.tool(
        name="hora_rasi_card",
        description="Chat card for one day across the 12 rasis: which rasis are in "
        "Chandrashtama and when, the best rasis, and every rasi's day percentage." + _COMMON,
    )
    async def hora_rasi_card(
        ctx: Context,
        date: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        tz: str | None = None,
        convention: Convention | None = None,
        ayanamsa: Ayanamsa | None = None,
    ) -> dict[str, Any]:
        params = {
            "date": date, "lat": lat, "lon": lon, "tz": tz,
            "convention": convention, "ayanamsa": ayanamsa,
        }  # fmt: skip
        result: dict[str, Any] = await api.get("/v1/cards/rasi", params, caller_key(ctx))
        return result

    @server.tool(
        name="hora_personal_card",
        description="Chat card for a stored profile: best windows (overall, before noon, after "
        "sunset), why horas are fully blocked (including Chandrashtama), and the day's "
        "tarabala and chandrabala with change times. `profile_id` must be an id known to the "
        "API." + _COMMON,
    )
    async def hora_personal_card(
        ctx: Context,
        profile_id: str,
        date: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        tz: str | None = None,
        convention: Convention | None = None,
        ayanamsa: Ayanamsa | None = None,
    ) -> dict[str, Any]:
        params = {
            "profile_id": profile_id, "date": date, "lat": lat, "lon": lon, "tz": tz,
            "convention": convention, "ayanamsa": ayanamsa,
        }  # fmt: skip
        result: dict[str, Any] = await api.get("/v1/cards/personal", params, caller_key(ctx))
        return result

    @server.tool(
        name="hora_personal_horas",
        description="All 24 horas scored 0-100 for a stored profile (null when fully blocked "
        "by an inauspicious window), with clean parts, blocked reasons, tarabala and "
        "chandrabala details, and the top windows: best overall, best before noon and best "
        "after sunset. `profile_id` must be an id known to the API." + _COMMON,
    )
    async def hora_personal_horas(
        ctx: Context,
        profile_id: str,
        date: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        tz: str | None = None,
        convention: Convention | None = None,
        ayanamsa: Ayanamsa | None = None,
    ) -> dict[str, Any]:
        params = {
            "profile_id": profile_id, "date": date, "lat": lat, "lon": lon, "tz": tz,
            "convention": convention, "ayanamsa": ayanamsa,
        }  # fmt: skip
        result: dict[str, Any] = await api.get("/v1/horas/personal", params, caller_key(ctx))
        return result

    return server


def build_app(settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    """The streamable-HTTP ASGI app (endpoint /mcp) with the configured access check.

    Loopback only may run without a check; anything wider needs HORA_MCP_TOKEN (one shared token)
    or HORA_MCP_PASSTHROUGH (each caller's own hora-api key).
    """
    if settings.token and settings.passthrough:
        raise ValueError("set HORA_MCP_TOKEN or HORA_MCP_PASSTHROUGH, not both")
    loopback = settings.host in {"127.0.0.1", "localhost", "::1"}
    if not (settings.token or settings.passthrough or loopback):
        raise ValueError(
            f"refusing to listen on {settings.host} without HORA_MCP_TOKEN or HORA_MCP_PASSTHROUGH"
        )
    server = create_server(settings, transport)
    security = None
    if settings.allowed_hosts:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.allowed_hosts),
            allowed_origins=[f"http://{h}" for h in settings.allowed_hosts],
        )
    app = server.streamable_http_app(host=settings.host, transport_security=security)
    if settings.passthrough:
        app.add_middleware(RequireBearer)
    elif settings.token:
        app.add_middleware(BearerAuth, token=settings.token)
    return app


def main() -> None:
    # httpx logs every request URL at INFO, which would put coordinates and profile ids in logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    uvicorn.run(build_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
