"""hora-mcp tests: the MCP protocol end to end with the hora-api HTTP API stubbed."""

import json
from typing import Any

import httpx
import pytest
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from hora_mcp.client import HoraApi, HoraApiError
from hora_mcp.server import build_app, create_server
from hora_mcp.settings import Settings

CARD = {"kind": "day", "title": "Wednesday 30 Sep 2026", "sections": [{"id": "sun", "rows": []}]}


class Upstream:
    """Records requests and replies from a table of canned responses."""

    def __init__(self, responses: dict[str, httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.responses = responses or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.get(request.url.path, httpx.Response(200, json=CARD))

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def problem(status: int, title: str, detail: str, **extra: Any) -> httpx.Response:
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail, **extra}
    return httpx.Response(status, json=body, headers={"content-type": "application/problem+json"})


async def test_lists_the_tools() -> None:
    server = create_server(Settings(), Upstream().transport)
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {
        "hora_day_card", "hora_rasi_card", "hora_personal_card", "hora_personal_horas",
    }  # fmt: skip
    assert tools["hora_personal_horas"].input_schema["required"] == ["profile_id"]
    assert tools["hora_personal_card"].input_schema["required"] == ["profile_id"]
    assert "required" not in tools["hora_day_card"].input_schema
    schema = tools["hora_day_card"].input_schema["properties"]
    assert set(schema) == {"date", "lat", "lon", "tz", "convention", "ayanamsa"}
    assert "Chandrashtama" in (tools["hora_rasi_card"].description or "")


async def test_day_card_calls_the_cards_endpoint() -> None:
    up = Upstream()
    async with Client(create_server(Settings(), up.transport)) as client:
        result = await client.call_tool(
            "hora_day_card",
            {"date": "2026-09-30", "lat": 3.107, "lon": 101.606, "tz": "Asia/Kuala_Lumpur"},
        )
    assert not result.is_error and result.structured_content == CARD
    (request,) = up.requests
    assert request.url.path == "/v1/cards/day" and request.method == "GET"
    assert dict(request.url.params) == {
        "date": "2026-09-30", "lat": "3.107", "lon": "101.606", "tz": "Asia/Kuala_Lumpur",
    }  # fmt: skip


async def test_omitted_arguments_are_not_sent() -> None:
    up = Upstream()
    async with Client(create_server(Settings(), up.transport)) as client:
        await client.call_tool("hora_rasi_card", {})
        await client.call_tool("hora_day_card", {"convention": "classical", "ayanamsa": "kp"})
    assert up.requests[0].url.path == "/v1/cards/rasi" and dict(up.requests[0].url.params) == {}
    assert dict(up.requests[1].url.params) == {"convention": "classical", "ayanamsa": "kp"}


async def test_personal_horas_passes_profile_id() -> None:
    reply = {"top": {"best_overall": {"lord": "Saturn", "score": 100.0}}}
    up = Upstream({"/v1/horas/personal": httpx.Response(200, json=reply)})
    async with Client(create_server(Settings(), up.transport)) as client:
        result = await client.call_tool(
            "hora_personal_horas", {"profile_id": "golden", "date": "2026-09-30"}
        )
    assert result.structured_content == reply
    assert dict(up.requests[0].url.params) == {"profile_id": "golden", "date": "2026-09-30"}
    assert up.requests[0].url.path == "/v1/horas/personal"


async def test_personal_card_calls_the_personal_cards_endpoint() -> None:
    card = {"kind": "personal", "title": "Golden (fixture) · Wednesday 30 Sep 2026", "sections": []}
    up = Upstream({"/v1/cards/personal": httpx.Response(200, json=card)})
    async with Client(create_server(Settings(), up.transport)) as client:
        result = await client.call_tool(
            "hora_personal_card", {"profile_id": "golden", "tz": "Asia/Kuala_Lumpur"}
        )
        missing = await client.call_tool("hora_personal_card", {})
    assert not result.is_error and result.structured_content == card
    assert up.requests[0].url.path == "/v1/cards/personal"
    assert dict(up.requests[0].url.params) == {"profile_id": "golden", "tz": "Asia/Kuala_Lumpur"}
    assert missing.is_error and len(up.requests) == 1  # profile_id is required; API not called


async def test_personal_card_unknown_profile_reaches_the_model() -> None:
    up = Upstream({"/v1/cards/personal": problem(404, "Profile not found", "No profile 'x'.")})
    async with Client(create_server(Settings(), up.transport)) as client:
        result = await client.call_tool("hora_personal_card", {"profile_id": "x"})
    assert result.is_error and "404 Profile not found: No profile 'x'." in str(result.content)


async def test_api_key_is_forwarded() -> None:
    up = Upstream()
    async with Client(create_server(Settings(api_key="secret"), up.transport)) as client:
        await client.call_tool("hora_day_card", {})
    assert up.requests[0].headers["x-api-key"] == "secret"
    up2 = Upstream()
    async with Client(create_server(Settings(), up2.transport)) as client:
        await client.call_tool("hora_day_card", {})
    assert "x-api-key" not in up2.requests[0].headers


async def test_api_problems_reach_the_model() -> None:
    up = Upstream({"/v1/horas/personal": problem(404, "Profile not found", "No profile 'x'.")})
    async with Client(create_server(Settings(), up.transport)) as client:
        result = await client.call_tool("hora_personal_horas", {"profile_id": "x"})
    assert result.is_error
    text = json.dumps([c.model_dump() for c in result.content])
    assert "404 Profile not found: No profile 'x'." in text


async def test_validation_problems_list_fields() -> None:
    errors = [{"loc": ["query", "lat"], "msg": "Input should be <= 90", "type": "less_than_equal"}]
    up = Upstream({"/v1/cards/day": problem(422, "Invalid request", "Bad.", errors=errors)})
    async with Client(create_server(Settings(), up.transport)) as client:
        result = await client.call_tool("hora_day_card", {"lat": 91})
    assert result.is_error and "query.lat: Input should be <= 90" in str(result.content)


async def test_unreachable_api_is_a_tool_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    server = create_server(Settings(api_url="http://hora.invalid"), httpx.MockTransport(refuse))
    async with Client(server) as client:
        result = await client.call_tool("hora_day_card", {})
    assert result.is_error and "cannot reach hora-api at http://hora.invalid" in str(result.content)


async def test_non_json_error_bodies() -> None:
    api = HoraApi(
        Settings(), httpx.MockTransport(lambda r: httpx.Response(502, text="bad gateway"))
    )
    with pytest.raises(HoraApiError, match="HTTP 502"):
        await api.get("/v1/day", {})
    await api.aclose()


def test_settings_from_env() -> None:
    s = Settings.from_env(
        {
            "HORA_API_URL": "http://hora.lan:8000/", "HORA_API_KEY": "k",
            "HORA_MCP_HOST": "0.0.0.0",
            "HORA_MCP_PORT": "9000", "HORA_MCP_TOKEN": "t",
            "HORA_MCP_ALLOWED_HOSTS": "hora.lan:9000, 192.168.1.20:9000",
        }
    )  # fmt: skip
    assert (s.api_url, s.api_key, s.host, s.port, s.token) == (
        "http://hora.lan:8000", "k", "0.0.0.0", 9000, "t",
    )  # fmt: skip
    assert s.allowed_hosts == ("hora.lan:9000", "192.168.1.20:9000")
    d = Settings.from_env({})
    assert (d.api_url, d.api_key, d.host, d.port, d.token) == (
        "http://127.0.0.1:8000", None, "127.0.0.1", 8765, None,
    )  # fmt: skip


# The streamable HTTP endpoint and its bearer token -------------------------------------------

INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}  # fmt: skip
HEADERS = {"content-type": "application/json", "accept": "application/json, text/event-stream"}


async def post_init(app: Any, headers: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765") as http,
    ):
        return await http.post("/mcp", json=INIT, headers={**HEADERS, **headers})


async def test_bearer_token_is_enforced() -> None:
    for headers in ({}, {"authorization": "Bearer nope"}, {"authorization": "Basic s3cret"}):
        app = build_app(Settings(token="s3cret"), Upstream().transport)  # one lifespan per app
        r = await post_init(app, headers)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


async def test_valid_token_and_no_token_configured() -> None:
    secured = build_app(Settings(token="s3cret"), Upstream().transport)
    ok = await post_init(secured, {"authorization": "Bearer s3cret"})
    assert ok.status_code == 200 and "hora-api" in ok.text
    open_app = build_app(Settings(), Upstream().transport)
    assert (await post_init(open_app, {})).status_code == 200


async def test_dns_rebinding_protection_follows_allowed_hosts() -> None:
    settings = Settings(host="0.0.0.0", allowed_hosts=("hora.lan:8765",), token="t")
    app = build_app(settings, Upstream().transport)
    headers = {**HEADERS, "authorization": "Bearer t"}
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport) as http,
    ):
        good = await http.post("http://hora.lan:8765/mcp", json=INIT, headers=headers)
        bad = await http.post("http://evil.example/mcp", json=INIT, headers=headers)
    assert good.status_code == 200 and bad.status_code == 421


# Passthrough: each caller's own bearer token is forwarded to the API as its key ---------------


async def call_over_http(app: Any, bearer: str | None, tool: str, arguments: dict[str, Any]) -> Any:
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8765",
            headers=headers,
        ) as http,
        Client(
            streamable_http_client("http://127.0.0.1:8765/mcp", http_client=http)  # type: ignore[arg-type]
        ) as client,
    ):
        return await client.call_tool(tool, arguments)


async def test_passthrough_forwards_each_callers_own_key() -> None:
    up = Upstream()
    app = build_app(Settings(passthrough=True, api_key="unused-owner-key"), up.transport)
    first = await call_over_http(app, "alice-key", "hora_day_card", {})
    app = build_app(Settings(passthrough=True), up.transport)
    second = await call_over_http(app, "bob-key", "hora_personal_card", {"profile_id": "b"})
    assert not first.is_error and not second.is_error
    assert [r.headers["x-api-key"] for r in up.requests] == ["alice-key", "bob-key"]
    assert "unused-owner-key" not in [r.headers.get("x-api-key") for r in up.requests]


async def test_passthrough_shows_the_apis_verdict_to_the_caller() -> None:
    forbidden = problem(403, "Paid tier required", "This endpoint needs a paid subscription.")
    up = Upstream({"/v1/cards/rasi": forbidden})
    app = build_app(Settings(passthrough=True), up.transport)
    result = await call_over_http(app, "free-key", "hora_rasi_card", {})
    assert result.is_error
    assert "403 Paid tier required: This endpoint needs a paid subscription." in str(result.content)


async def test_passthrough_refuses_requests_without_a_bearer_token() -> None:
    app = build_app(Settings(passthrough=True), Upstream().transport)
    r = await post_init(app, {})
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    ok = await post_init(
        build_app(Settings(passthrough=True), Upstream().transport), {"authorization": "Bearer k"}
    )
    assert ok.status_code == 200


def test_unsafe_configurations_are_refused() -> None:
    with pytest.raises(ValueError, match="not both"):
        build_app(Settings(token="t", passthrough=True))
    with pytest.raises(ValueError, match="refusing to listen on 0.0.0.0"):
        build_app(Settings(host="0.0.0.0"))
    build_app(Settings(host="0.0.0.0", token="t"))  # fine
    build_app(Settings(host="0.0.0.0", passthrough=True))  # fine
    build_app(Settings())  # loopback needs no check


def test_passthrough_setting_from_env() -> None:
    assert Settings.from_env({"HORA_MCP_PASSTHROUGH": "true"}).passthrough is True
    assert Settings.from_env({"HORA_MCP_PASSTHROUGH": "1"}).passthrough is True
    assert Settings.from_env({}).passthrough is False
    assert Settings.from_env({"HORA_MCP_PASSTHROUGH": "no"}).passthrough is False
