"""api-tiers: per-subscriber keys, free and paid tiers, profile scopes and revocation."""

import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest
import yaml
from fastapi.testclient import TestClient

from hora_api.api import keys as K
from hora_api.api.app import create_app
from hora_api.api.settings import ApiSettings

FIXTURE: dict[str, Any] = yaml.safe_load(
    (Path(__file__).parent / "fixtures" / "golden.yaml").read_text()
)
GOLDEN = FIXTURE["profile"]
OTHER = {**GOLDEN, "id": "other", "display_name": "Other (fixture)"}
PJ: dict[str, Any] = {
    "date": "2026-09-30", "lat": 3.107, "lon": 101.606, "tz": "Asia/Kuala_Lumpur",
}  # fmt: skip

FREE_ENDPOINTS = ["/v1/day", "/v1/cards/day"]
PAID_ENDPOINTS = [
    "/v1/horas/rasi", "/v1/cards/rasi", "/v1/profiles",
    "/v1/horas/personal?profile_id=golden", "/v1/cards/personal?profile_id=golden",
]  # fmt: skip


def entry(
    key: str, key_id: str, tier: str, profiles: list[str], revoked: bool = False
) -> dict[str, Any]:
    return {
        "id": key_id, "hash": K.hash_key(key), "tier": tier, "profiles": profiles,
        "revoked": revoked,
    }  # fmt: skip


class Env:
    """A running API with a keys file the test can edit."""

    def __init__(self, tmp_path: Path, entries: list[dict[str, Any]], **settings: Any) -> None:
        self.keys_path = tmp_path / "keys.yaml"
        self.write(entries)
        profiles = tmp_path / "profiles.yaml"
        profiles.write_text(yaml.safe_dump({"profiles": [GOLDEN, OTHER]}))
        cfg = ApiSettings(profiles_path=profiles, keys_path=self.keys_path, **settings)
        self.client = TestClient(create_app(cfg))

    def write(self, entries: list[dict[str, Any]]) -> None:
        self.keys_path.write_text(yaml.safe_dump({"keys": entries}))
        st = self.keys_path.stat()  # make sure the change is seen even within one mtime tick
        os.utime(self.keys_path, (st.st_atime, st.st_mtime + 5))

    def get(self, path: str, key: str | None = None) -> Any:
        url = urlsplit(path)
        params = {**PJ, **dict(parse_qsl(url.query))}  # the path may carry its own query
        headers = {"X-API-Key": key} if key else {}
        return self.client.get(url.path, params=params, headers=headers)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(
        tmp_path,
        [
            entry("free-key", "alice-free", "free", []),
            entry("bob-key", "bob", "paid", ["golden"]),
            entry("carol-key", "carol", "paid", []),
            entry("all-key", "dave", "paid", ["*"]),
            entry("old-key", "erin", "paid", ["*"], revoked=True),
        ],
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_keys_are_required_once_a_keys_file_has_entries(env: Env) -> None:
    for key in (None, "nope", "old-key"):  # missing, unknown, revoked
        r = env.get("/v1/day", key)
        assert r.status_code == 401, key
        assert r.headers["content-type"] == "application/problem+json"
        assert r.headers["www-authenticate"] == "ApiKey"
    assert env.get("/v1/day", "free-key").status_code == 200
    assert env.client.get("/healthz").status_code == 200  # health checks stay open


def test_owner_keys_from_api_keys_still_work(tmp_path: Path) -> None:
    env = Env(tmp_path, [entry("free-key", "alice", "free", [])], api_keys="owner-secret")
    for path in FREE_ENDPOINTS + PAID_ENDPOINTS:
        assert env.get(path, "owner-secret").status_code == 200, path
    assert env.get("/v1/profiles", "free-key").status_code == 403  # the file's keys keep tiers


def test_authentication_is_off_with_no_keys_anywhere(tmp_path: Path) -> None:
    env = Env(tmp_path, [])
    assert env.get("/v1/profiles").status_code == 200
    assert len(env.get("/v1/profiles").json()["profiles"]) == 2


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------


def test_free_key_gets_the_day_endpoints_only(env: Env) -> None:
    for path in FREE_ENDPOINTS:
        assert env.get(path, "free-key").status_code == 200, path
    for path in PAID_ENDPOINTS:
        r = env.get(path, "free-key")
        assert r.status_code == 403, path
        assert r.headers["content-type"] == "application/problem+json"
        body = r.json()
        assert body["type"] == "urn:hora-api:problem:tier-required"
        assert body["title"] == "Paid tier required" and "paid subscription" in body["detail"]
        assert (body["tier"], body["required_tier"]) == ("free", "paid")
    post = env.client.post(
        "/v1/horas/personal", params=PJ, json=GOLDEN, headers={"X-API-Key": "free-key"}
    )
    assert post.status_code == 403


def test_paid_key_gets_everything(env: Env) -> None:
    for path in FREE_ENDPOINTS + PAID_ENDPOINTS:
        assert env.get(path, "bob-key").status_code == 200, path


def test_a_bad_key_is_401_before_any_tier_check(env: Env) -> None:
    assert env.get("/v1/horas/rasi", "nope").status_code == 401  # not 403


# ---------------------------------------------------------------------------
# Profile scopes
# ---------------------------------------------------------------------------


def test_a_key_sees_only_its_own_profiles(env: Env) -> None:
    listing = env.get("/v1/profiles", "bob-key").json()["profiles"]
    assert [p["id"] for p in listing] == ["golden"]
    assert env.get("/v1/profiles", "carol-key").json() == {"profiles": []}
    assert sorted(p["id"] for p in env.get("/v1/profiles", "all-key").json()["profiles"]) == [
        "golden", "other",
    ]  # fmt: skip


def test_out_of_scope_profiles_look_like_unknown_ones(env: Env) -> None:
    for path in ("/v1/horas/personal", "/v1/cards/personal"):
        params = {**PJ, "profile_id": "other"}
        forbidden = env.client.get(path, params=params, headers={"X-API-Key": "bob-key"})
        unknown = env.client.get(
            path, params={**PJ, "profile_id": "nobody"}, headers={"X-API-Key": "bob-key"}
        )
        assert forbidden.status_code == unknown.status_code == 404
        assert forbidden.json()["type"] == "urn:hora-api:problem:profile-not-found"
        assert forbidden.json()["title"] == unknown.json()["title"]  # no existence leak
        ok = env.client.get(
            path, params={**PJ, "profile_id": "golden"}, headers={"X-API-Key": "bob-key"}
        )
        assert ok.status_code == 200


def test_a_paid_key_without_profiles_can_still_send_an_inline_profile(env: Env) -> None:
    r = env.client.get(
        "/v1/horas/personal",
        params={**PJ, "profile_id": "golden"},
        headers={"X-API-Key": "carol-key"},
    )
    assert r.status_code == 404
    post = env.client.post(
        "/v1/horas/personal", params=PJ, json=GOLDEN, headers={"X-API-Key": "carol-key"}
    )
    assert post.status_code == 200 and post.json()["profile"]["id"] == "golden"


# ---------------------------------------------------------------------------
# Revocation and the keys file
# ---------------------------------------------------------------------------


def test_revoking_a_key_takes_effect_on_the_next_request(env: Env) -> None:
    assert env.get("/v1/horas/rasi", "bob-key").status_code == 200
    env.write([entry("bob-key", "bob", "paid", ["golden"], revoked=True)])
    assert env.get("/v1/horas/rasi", "bob-key").status_code == 401
    env.write([entry("bob-key", "bob", "free", ["golden"])])  # downgraded, not revoked
    assert env.get("/v1/day", "bob-key").status_code == 200
    assert env.get("/v1/horas/rasi", "bob-key").status_code == 403


def test_a_new_key_works_without_a_restart(env: Env) -> None:
    assert env.get("/v1/day", "late-key").status_code == 401
    env.write([entry("late-key", "late", "free", [])])
    assert env.get("/v1/day", "late-key").status_code == 200


def test_a_broken_keys_file_fails_closed(env: Env) -> None:
    env.keys_path.write_text("keys: [ {id: x}\n")
    os.utime(env.keys_path, (0, env.keys_path.stat().st_mtime + 10))
    for key in ("bob-key", "nope", None):
        r = env.get("/v1/day", key)
        assert r.status_code == 503 and r.json()["type"] == "urn:hora-api:problem:keys-unavailable"
    assert env.client.get("/healthz").status_code == 200
    ready = env.client.get("/readyz")
    assert ready.status_code == 503 and ready.json()["title"] == "Keys unavailable"


def test_a_keys_file_with_only_revoked_keys_still_requires_a_key(tmp_path: Path) -> None:
    env = Env(tmp_path, [entry("gone", "gone", "paid", ["*"], revoked=True)])
    assert env.get("/v1/day").status_code == 401  # never falls back to open


def test_key_ids_but_not_keys_are_logged(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    env.get("/v1/day", "bob-key")
    env.get("/v1/day", "nope-secret")
    out = capsys.readouterr().out
    assert "bob" in out and "bob-key" not in out and "nope-secret" not in out


def test_openapi_documents_the_tier_error(env: Env) -> None:
    spec = env.client.get("/v1/openapi.json", headers={"X-API-Key": "free-key"}).json()
    assert "403" in spec["paths"]["/v1/horas/rasi"]["get"]["responses"]
    assert "401" in spec["paths"]["/v1/day"]["get"]["responses"]


# ---------------------------------------------------------------------------
# The key file format and hora-keys
# ---------------------------------------------------------------------------


def test_hash_and_principal() -> None:
    digest = K.hash_key("abc")
    assert digest.startswith("sha256:") and len(digest) == 71 and "abc" not in digest
    p = K.Principal("x", "paid", frozenset({"a"}))
    assert p.can_use("a") and not p.can_use("b") and p.is_paid
    assert K.OWNER.can_use("anything") and not K.Principal("f", "free", frozenset()).is_paid


def test_read_entries_validation(tmp_path: Path) -> None:
    path = tmp_path / "keys.yaml"
    assert K.read_entries(path) == []  # missing
    path.write_text("")
    assert K.read_entries(path) == []
    good = entry("k", "a", "free", [])
    for bad, message in (
        ({"keys": [{**good, "hash": "md5:abc"}]}, "key #1 is invalid"),
        ({"keys": [{**good, "tier": "gold"}]}, "key #1 is invalid"),
        ({"keys": [good, {**good, "hash": K.hash_key("z")}]}, "duplicate key ids"),
        ({"keys": [good, {**good, "id": "b"}]}, "duplicate key hashes"),
        ({"keys": "nope"}, "expected a 'keys:' list"),
    ):
        path.write_text(yaml.safe_dump(bad))
        with pytest.raises(K.KeyFileError, match=message):
            K.read_entries(path)
    path.write_text("keys: [")
    with pytest.raises(K.KeyFileError, match="invalid YAML"):
        K.read_entries(path)


def test_store_lookup_checks_env_keys_and_the_file(tmp_path: Path) -> None:
    path = tmp_path / "keys.yaml"
    path.write_text(yaml.safe_dump({"keys": [entry("file-key", "f", "free", ["p"])]}))
    store = K.KeyStore(path, frozenset({"env-key"}))
    assert store.lookup("env-key") == K.OWNER
    assert store.lookup("file-key") == K.Principal("f", "free", frozenset({"p"}))
    assert store.lookup("other") is None and store.lookup(None) is None and store.lookup("") is None
    assert store.auth_required()
    assert not K.KeyStore(tmp_path / "absent.yaml").auth_required()


def test_hora_keys_cli_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "keys.yaml"
    assert (
        K.main(["--file", str(path), "add", "--id", "zed", "--tier", "paid", "--profiles", "a, b"])
        == 0
    )
    out = capsys.readouterr().out
    key = out.split("Key (shown once, store it now): ")[1].strip()
    assert len(key) >= 32 and key not in path.read_text()  # only the hash is stored
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    store = K.KeyStore(path)
    assert store.lookup(key) == K.Principal("zed", "paid", frozenset({"a", "b"}))

    assert K.main(["--file", str(path), "add", "--id", "zed", "--tier", "free"]) == 1  # duplicate
    assert "already exists" in capsys.readouterr().err
    assert K.main(["--file", str(path), "list"]) == 0
    listing = capsys.readouterr().out
    assert "zed" in listing and "paid" in listing and "active" in listing
    assert key not in listing and "sha256" not in listing

    assert K.main(["--file", str(path), "revoke", "zed"]) == 0
    assert K.KeyStore(path).lookup(key) is None
    assert K.main(["--file", str(path), "restore", "zed"]) == 0
    assert K.KeyStore(path).lookup(key) is not None
    assert K.main(["--file", str(path), "revoke", "ghost"]) == 1


def test_a_generated_key_works_against_the_api(tmp_path: Path) -> None:
    env = Env(tmp_path, [])
    key = K.add_key(env.keys_path, "new", "free", [])
    assert env.get("/v1/day", key).status_code == 200
    assert env.get("/v1/day").status_code == 401  # a key now exists: open access is over
    assert env.get("/v1/horas/rasi", key).status_code == 403
