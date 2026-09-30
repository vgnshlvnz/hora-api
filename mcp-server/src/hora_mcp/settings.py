"""Configuration from the environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 30.0
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    # The hora-api HTTP API this server wraps, and its optional X-API-Key.
    api_url: str = DEFAULT_API_URL
    api_key: str | None = None
    timeout: float = DEFAULT_TIMEOUT

    # Where this MCP server listens. Loopback by default: to reach it from other machines set
    # HORA_MCP_HOST (for example 0.0.0.0), HORA_MCP_ALLOWED_HOSTS and HORA_MCP_TOKEN.
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    # Bearer token clients must send as "Authorization: Bearer <token>"; None turns it off.
    token: str | None = None
    # Forward each caller's own bearer token to the API as its X-API-Key, so the API (not this
    # server) decides who the caller is and what tier they have. Replaces the static token above.
    passthrough: bool = False
    # Extra Host header values (for DNS-rebinding protection) when not on loopback, e.g.
    # "hora.home:8765,192.168.1.20:8765".
    allowed_hosts: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        return cls(
            api_url=e.get("HORA_API_URL", DEFAULT_API_URL).rstrip("/"),
            api_key=e.get("HORA_API_KEY") or None,
            timeout=float(e.get("HORA_API_TIMEOUT", DEFAULT_TIMEOUT)),
            host=e.get("HORA_MCP_HOST", DEFAULT_HOST),
            port=int(e.get("HORA_MCP_PORT", DEFAULT_PORT)),
            token=e.get("HORA_MCP_TOKEN") or None,
            passthrough=e.get("HORA_MCP_PASSTHROUGH", "").strip().lower() in {"1", "true", "yes"},
            allowed_hosts=tuple(_csv(e.get("HORA_MCP_ALLOWED_HOSTS", ""))),
        )
