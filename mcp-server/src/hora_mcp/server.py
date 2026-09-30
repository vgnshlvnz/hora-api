"""The MCP server: three tools over hora-api, served over streamable HTTP."""

from __future__ import annotations

import hmac
import logging
from typing import Any, Literal

import httpx
import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from hora_mcp import __version__
from hora_mcp.client import HoraApi
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


def create_server(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> MCPServer:
    """Build the MCP server. `transport` lets tests stand in for the HTTP API."""
    api = HoraApi(settings, transport)
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
        result: dict[str, Any] = await api.get("/v1/cards/day", params)
        return result

    @server.tool(
        name="hora_rasi_card",
        description="Chat card for one day across the 12 rasis: which rasis are in "
        "Chandrashtama and when, the best rasis, and every rasi's day percentage." + _COMMON,
    )
    async def hora_rasi_card(
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
        result: dict[str, Any] = await api.get("/v1/cards/rasi", params)
        return result

    @server.tool(
        name="hora_personal_horas",
        description="All 24 horas scored 0-100 for a stored profile (null when fully blocked "
        "by an inauspicious window), with clean parts, blocked reasons, tarabala and "
        "chandrabala details, and the top windows: best overall, best before noon and best "
        "after sunset. `profile_id` must be an id known to the API." + _COMMON,
    )
    async def hora_personal_horas(
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
        result: dict[str, Any] = await api.get("/v1/horas/personal", params)
        return result

    return server


def build_app(settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    """The streamable-HTTP ASGI app (endpoint /mcp), with the bearer token check if configured."""
    server = create_server(settings, transport)
    security = None
    if settings.allowed_hosts:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.allowed_hosts),
            allowed_origins=[f"http://{h}" for h in settings.allowed_hosts],
        )
    app = server.streamable_http_app(host=settings.host, transport_security=security)
    if settings.token:
        app.add_middleware(BearerAuth, token=settings.token)
    return app


def main() -> None:
    # httpx logs every request URL at INFO, which would put coordinates and profile ids in logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    uvicorn.run(build_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
