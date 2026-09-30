"""API configuration from the environment (no prefix: PROFILES_PATH, API_KEYS, ...)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Defaults for requests that omit lat/lon/tz: Petaling Jaya.
    default_lat: float = 3.107
    default_lon: float = 101.606
    default_tz: str = "Asia/Kuala_Lumpur"

    # Real profiles live outside the repo.
    profiles_path: Path = Path("~/.config/hora-api/profiles.yaml")

    # Comma-separated owner keys (paid, every profile). With no keys here and no keys file,
    # authentication is off.
    api_keys: str = ""

    # Per-subscriber keys with tiers and profile scopes, kept outside the repo. See api/keys.py.
    keys_path: Path = Path("~/.config/hora-api/keys.yaml")

    # Override the directory holding the classical tables (default: the repo's data/).
    data_dir: Path | None = None

    cache_size: int = 128
    # Shortest clean stretch worth reporting as a recommended window.
    min_window_minutes: int = 15

    @property
    def key_set(self) -> frozenset[str]:
        return frozenset(k.strip() for k in self.api_keys.split(",") if k.strip())

    @property
    def keys_file(self) -> Path:
        return self.keys_path.expanduser()

    @property
    def profiles_file(self) -> Path:
        return self.profiles_path.expanduser()
