"""Thin async client for the hora-api HTTP API."""

from __future__ import annotations

from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from hora_mcp.settings import Settings


class HoraApiError(ToolError):
    """The API refused or could not be reached. As a ToolError its message reaches the model."""


def _problem_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"hora-api returned HTTP {response.status_code}"
    if not isinstance(body, dict):
        return f"hora-api returned HTTP {response.status_code}"
    title = body.get("title") or f"HTTP {response.status_code}"
    detail = body.get("detail")
    errors = body.get("errors")
    message = f"{response.status_code} {title}" + (f": {detail}" if detail else "")
    if isinstance(errors, list) and errors:
        fields = "; ".join(f"{'.'.join(e.get('loc', []))}: {e.get('msg')}" for e in errors)
        message += f" ({fields})"
    return message


class HoraApi:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        headers = {"Accept": "application/json"}
        if settings.api_key:
            headers["X-API-Key"] = settings.api_key
        self._base_url = settings.api_url
        self._http = httpx.AsyncClient(
            base_url=settings.api_url,
            headers=headers,
            timeout=settings.timeout,
            transport=transport,
        )

    async def get(self, path: str, params: dict[str, Any], api_key: str | None = None) -> Any:
        """GET `path` with the non-None `params`; raise HoraApiError on any failure.

        `api_key` replaces the configured key for this call (the caller's own, in passthrough).
        """
        query = {k: v for k, v in params.items() if v is not None}
        headers = {"X-API-Key": api_key} if api_key else None
        try:
            response = await self._http.get(path, params=query, headers=headers)
        except httpx.HTTPError as e:
            raise HoraApiError(f"cannot reach hora-api at {self._base_url}: {e}") from e
        if response.is_success:
            return response.json()
        raise HoraApiError(_problem_message(response))

    async def aclose(self) -> None:
        await self._http.aclose()
