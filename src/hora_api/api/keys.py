"""Per-subscriber API keys with tiers, kept in a file outside the repo.

    keys:
      - id: alice                       # a label for logs; not a secret
        hash: sha256:<hex of the key>   # the key itself is never stored
        tier: paid                      # free or paid
        profiles: [alice-me]            # stored profile ids this key may use; "*" means all
        revoked: false

Tiers: a free key may use only the day endpoints; a paid key may also use the rest. Stored
profiles are scoped per key (a paid key with no `profiles` can only send inline profiles).
Keys listed in API_KEYS keep working and are owner keys (paid, every profile). With neither
API_KEYS nor a keys file, authentication is off and everyone is the local owner.

The file is re-read when it changes, so revoking a key takes effect on the next request. A file
that cannot be read fails closed (KeyFileError), never open. `hora-keys` manages the file.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
import secrets
import sys
import tempfile
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

Tier = Literal["free", "paid"]
ALL_PROFILES = "*"
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")


class KeyFileError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is calling: a key's id, its tier and the stored profiles it may use."""

    id: str
    tier: Tier
    profiles: frozenset[str]

    @property
    def is_paid(self) -> bool:
        return self.tier == "paid"

    def can_use(self, profile_id: str) -> bool:
        return ALL_PROFILES in self.profiles or profile_id in self.profiles


OWNER = Principal("owner", "paid", frozenset({ALL_PROFILES}))
LOCAL = Principal("local", "paid", frozenset({ALL_PROFILES}))  # authentication is off


def hash_key(key: str) -> str:
    """Keys are random and long, so a plain SHA-256 is enough; no password hashing needed."""
    return "sha256:" + hashlib.sha256(key.encode()).hexdigest()


class KeyEntry(BaseModel):
    id: str
    hash: str
    tier: Tier
    profiles: list[str] = Field(default_factory=list)
    revoked: bool = False
    created: str | None = None

    @field_validator("hash")
    @classmethod
    def _valid_hash(cls, v: str) -> str:
        if not _HASH.match(v):
            raise ValueError("hash must be 'sha256:' followed by 64 hex digits")
        return v


def read_entries(path: Path) -> list[KeyEntry]:
    """Parse the keys file; a missing file is an empty list, a bad one raises KeyFileError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as e:
        raise KeyFileError(f"{path}: cannot read file") from e
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise KeyFileError(f"{path}: invalid YAML") from e
    if doc is None:
        return []
    if not isinstance(doc, dict) or not isinstance(doc.get("keys", []), list):
        raise KeyFileError(f"{path}: expected a 'keys:' list")
    entries: list[KeyEntry] = []
    for i, raw in enumerate(doc.get("keys", [])):
        try:
            entries.append(KeyEntry.model_validate(raw))
        except ValidationError as e:
            raise KeyFileError(f"{path}: key #{i + 1} is invalid") from e
    ids = [e.id for e in entries]
    if len(set(ids)) != len(ids):
        raise KeyFileError(f"{path}: duplicate key ids")
    if len({e.hash for e in entries}) != len(entries):
        raise KeyFileError(f"{path}: duplicate key hashes")
    return entries


class KeyStore:
    def __init__(self, path: Path, env_keys: frozenset[str] = frozenset()) -> None:
        self._path = path
        self._env_hashes = {hash_key(k): OWNER for k in env_keys}
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._entries: list[KeyEntry] = []

    def entries(self) -> list[KeyEntry]:
        """The keys file's entries, reloaded when the file appeared, changed or vanished."""
        with self._lock:
            try:
                mtime: float | None = self._path.stat().st_mtime
            except FileNotFoundError:
                mtime = None
            if mtime != self._mtime:
                self._entries = [] if mtime is None else read_entries(self._path)
                self._mtime = mtime
            return self._entries

    def auth_required(self) -> bool:
        """True once any key exists (even a revoked one): then anonymous access is refused."""
        return bool(self._env_hashes) or bool(self.entries())

    def lookup(self, key: str | None) -> Principal | None:
        """The principal for a presented key, or None if it is missing, unknown or revoked."""
        if not key:
            return None
        digest = hash_key(key)
        found: Principal | None = None
        # Compare against every stored hash so timing does not reveal which one is close.
        for stored, principal in self._env_hashes.items():
            if hmac.compare_digest(digest, stored):
                found = principal
        for entry in self.entries():
            if hmac.compare_digest(digest, entry.hash) and not entry.revoked:
                found = Principal(entry.id, entry.tier, frozenset(entry.profiles))
        return found


# ---------------------------------------------------------------------------
# hora-keys: manage the keys file
# ---------------------------------------------------------------------------


def default_keys_path() -> Path:
    return Path(os.environ.get("KEYS_PATH", "~/.config/hora-api/keys.yaml")).expanduser()


def _write(path: Path, entries: list[KeyEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(
        {"keys": [e.model_dump(exclude_none=True) for e in entries]}, sort_keys=False
    )
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".keys-")
    with os.fdopen(fd, "w") as f:  # mkstemp creates the file with mode 0600
        f.write(body)
    os.replace(tmp, path)


def add_key(path: Path, key_id: str, tier: Tier, profiles: list[str]) -> str:
    """Create a key, store only its hash, and return the key (shown once)."""
    entries = read_entries(path)
    if any(e.id == key_id for e in entries):
        raise KeyFileError(f"a key with id {key_id!r} already exists")
    key = secrets.token_urlsafe(24)
    entries.append(
        KeyEntry(
            id=key_id,
            hash=hash_key(key),
            tier=tier,
            profiles=profiles,
            created=datetime.now(UTC).date().isoformat(),
        )  # fmt: skip
    )
    _write(path, entries)
    return key


def set_revoked(path: Path, key_id: str, revoked: bool) -> None:
    entries = read_entries(path)
    for entry in entries:
        if entry.id == key_id:
            entry.revoked = revoked
            _write(path, entries)
            return
    raise KeyFileError(f"no key with id {key_id!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hora-keys", description="Manage hora-api keys.")
    parser.add_argument("--file", type=Path, default=None, help="keys file (default: $KEYS_PATH)")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="create a key; the key is printed once")
    add.add_argument("--id", required=True, dest="key_id")
    add.add_argument("--tier", choices=["free", "paid"], required=True)
    add.add_argument("--profiles", default="", help="comma-separated stored profile ids, or *")
    revoke = sub.add_parser("revoke", help="revoke a key (takes effect on the next request)")
    revoke.add_argument("key_id")
    restore = sub.add_parser("restore", help="undo a revocation")
    restore.add_argument("key_id")
    sub.add_parser("list", help="list keys (never shows keys or hashes)")
    args = parser.parse_args(argv)
    path = args.file or default_keys_path()

    try:
        if args.command == "add":
            profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
            key = add_key(path, args.key_id, args.tier, profiles)
            print(f"Added {args.key_id!r} ({args.tier}) to {path}")
            print(f"Key (shown once, store it now): {key}")
        elif args.command in ("revoke", "restore"):
            set_revoked(path, args.key_id, args.command == "revoke")
            print(f"{args.command.capitalize()}d {args.key_id!r}")
        else:
            for e in read_entries(path):
                state = "revoked" if e.revoked else "active"
                print(f"{e.id:20} {e.tier:5} {state:8} profiles={','.join(e.profiles) or '-'}")
    except KeyFileError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
