"""Profile store: profiles live in a YAML file outside the repo, reloaded when it changes.

File format:

    profiles:
      - id: me
        display_name: Me
        janma_nakshatra: Rohini     # name or 0-26
        janma_rasi: Vrishabha       # name or 0-11
        lagna: Kumbha               # name or 0-11
        tz_home: Asia/Kuala_Lumpur
        dasha: [...]                # optional

A missing file is an empty store; an unreadable or invalid one raises ProfileFileError.
"""

from __future__ import annotations

import threading
from pathlib import Path

import yaml
from pydantic import ValidationError

from hora_api.scoring.personal import Profile


class ProfileFileError(Exception):
    pass


class ProfileStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._profiles: dict[str, Profile] = {}

    def _read(self) -> dict[str, Profile]:
        try:
            doc = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ProfileFileError(f"{self._path}: invalid YAML") from e
        except OSError as e:
            raise ProfileFileError(f"{self._path}: cannot read file") from e
        if doc is None:
            return {}
        if not isinstance(doc, dict) or not isinstance(doc.get("profiles", []), list):
            raise ProfileFileError(f"{self._path}: expected a 'profiles:' list")
        found: dict[str, Profile] = {}
        for i, raw in enumerate(doc.get("profiles", [])):
            try:
                profile = Profile.model_validate(raw)
            except ValidationError as e:
                raise ProfileFileError(f"{self._path}: profile #{i + 1} is invalid") from e
            if profile.id in found:
                raise ProfileFileError(f"{self._path}: duplicate profile id {profile.id!r}")
            found[profile.id] = profile
        return found

    def get(self) -> dict[str, Profile]:
        """Current profiles, reloading if the file appeared, changed or vanished."""
        with self._lock:
            try:
                mtime: float | None = self._path.stat().st_mtime
            except FileNotFoundError:
                mtime = None
            if mtime != self._mtime or (mtime is None and self._profiles):
                self._profiles = {} if mtime is None else self._read()
                self._mtime = mtime
            return self._profiles
