"""http-api contract tests: the golden PJ day (Wed 2026-09-30) through the HTTP layer."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from hora_api.api.app import create_app
from hora_api.api.service import Services
from hora_api.api.settings import ApiSettings

KL = ZoneInfo("Asia/Kuala_Lumpur")
FIXTURE: dict[str, Any] = yaml.safe_load(
    (Path(__file__).parent / "fixtures" / "golden.yaml").read_text()
)
GOLDEN_PROFILE: dict[str, Any] = FIXTURE["profile"]
PJ: dict[str, Any] = {
    "date": "2026-09-30", "lat": 3.107, "lon": 101.606, "tz": "Asia/Kuala_Lumpur",
}  # fmt: skip


def make_client(tmp_path: Path, **overrides: Any) -> TestClient:
    profiles = tmp_path / "profiles.yaml"
    if "profiles_path" not in overrides:
        # An extra stray key must never reach any response.
        entry = {**GOLDEN_PROFILE, "birth_note": "not for output"}
        profiles.write_text(yaml.safe_dump({"profiles": [entry]}))
        overrides["profiles_path"] = profiles
    return TestClient(create_app(ApiSettings(**overrides)))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with make_client(tmp_path) as c:
        yield c


def hhmm(iso: str) -> str:
    """Local HH:MM of an ISO time string, rounded to the nearest minute."""
    return (datetime.fromisoformat(iso).astimezone(KL) + timedelta(seconds=30)).strftime("%H:%M")


def minutes_from(iso: str, hh: int, mm: int) -> float:
    t = datetime.fromisoformat(iso).astimezone(KL)
    return abs((t - t.replace(hour=hh, minute=mm, second=0)).total_seconds()) / 60


# ---------------------------------------------------------------------------
# /v1/day
# ---------------------------------------------------------------------------


def test_golden_day(client: TestClient) -> None:
    r = client.get("/v1/day", params=PJ)
    assert r.status_code == 200 and r.headers["content-type"] == "application/json"
    j = r.json()
    assert j["meta"] == {
        "date": "2026-09-30", "weekday": "Wednesday", "tz": "Asia/Kuala_Lumpur", "lat": 3.107,
        "lon": 101.606, "convention": "tamil", "ayanamsa": "lahiri",
    }  # fmt: skip
    sun = j["sun"]
    assert sun["sunrise"].endswith("+08:00")  # output is in the request's timezone
    assert minutes_from(sun["sunrise"], 7, 2) <= 1 and minutes_from(sun["sunset"], 19, 5) <= 1
    assert minutes_from(sun["next_sunrise"], 7, 2) <= 1

    horas = j["horas"]
    assert [(hhmm(h["start"]), h["lord"]) for h in horas[:8]] == [
        ("07:02", "Mercury"), ("08:02", "Moon"), ("09:02", "Saturn"), ("10:02", "Jupiter"),
        ("11:02", "Mars"), ("12:02", "Sun"), ("13:02", "Venus"), ("14:02", "Mercury"),
    ]  # fmt: skip
    assert len(horas) == 24 and (hhmm(horas[-1]["start"]), horas[-1]["lord"]) == ("06:02", "Saturn")

    by_reason = {tuple(b["reasons"]): b for b in j["blocked"]}
    yama, rahu = by_reason[("yamagandam",)], by_reason[("rahu_kalam",)]
    assert minutes_from(yama["start"], 8, 32) <= 1 and minutes_from(yama["end"], 10, 3) <= 1
    assert minutes_from(rahu["end"], 14, 34) <= 1
    reasons = {r for b in j["blocked"] for r in b["reasons"]}
    assert reasons == {"rahu_kalam", "yamagandam", "gulika_kalam", "durmuhurta", "varjyam"}

    t = j["transitions"]
    assert [(x["kind"], x["from_index"], x["to_index"]) for x in t] == [
        ("nakshatra", 1, 2), ("rasi", 0, 1), ("tithi", 19, 20),
    ]  # fmt: skip
    assert (t[0]["from_name"], t[0]["to_name"]) == ("Bharani", "Krittika")
    assert (t[1]["from_name"], t[1]["to_name"]) == ("Mesha", "Vrishabha")
    assert t[2]["from_name"] is None
    # Verified ephemeris times (the brief said ~10:17, ~15:47, ~17:32).
    for x, (hh, mm) in zip(t, [(10, 7), (15, 44), (17, 26)], strict=True):
        assert minutes_from(x["time"], hh, mm) <= 2

    assert len(j["gowri"]) == 16 and {g["nature"] for g in j["gowri"]} <= {"good", "bad"}
    assert j["unverified_tables"] == ["durmuhurta", "gowri", "varjyam"]


def test_times_are_whole_seconds_and_contiguous(client: TestClient) -> None:
    horas = client.get("/v1/day", params=PJ).json()["horas"]
    assert all(datetime.fromisoformat(h["start"]).microsecond == 0 for h in horas)
    assert all(a["end"] == b["start"] for a, b in zip(horas, horas[1:], strict=False))


def test_defaults_come_from_settings(client: TestClient) -> None:
    j = client.get("/v1/day").json()
    assert (j["meta"]["lat"], j["meta"]["lon"], j["meta"]["tz"]) == (
        3.107,
        101.606,
        "Asia/Kuala_Lumpur",
    )
    assert j["meta"]["date"] == datetime.now(KL).date().isoformat()
    assert (j["meta"]["convention"], j["meta"]["ayanamsa"]) == ("tamil", "lahiri")


def test_output_uses_request_timezone(client: TestClient) -> None:
    # Same place and sunrise, expressed in IST: the local date is the same day in both zones.
    j = client.get("/v1/day", params={**PJ, "tz": "Asia/Kolkata"}).json()
    assert j["meta"]["tz"] == "Asia/Kolkata"
    assert j["sun"]["sunrise"].startswith("2026-09-30T04:31") and j["sun"]["sunrise"].endswith(
        "+05:30"
    )


def test_convention_and_ayanamsa(client: TestClient) -> None:
    tamil = client.get("/v1/day", params=PJ).json()
    classical = client.get("/v1/day", params={**PJ, "convention": "classical"}).json()
    assert classical["meta"]["convention"] == "classical"
    assert tamil["horas"][1]["start"] != classical["horas"][1]["start"]
    kp = client.get("/v1/day", params={**PJ, "ayanamsa": "kp"})
    assert kp.status_code == 200 and kp.json()["meta"]["ayanamsa"] == "kp"


@pytest.mark.parametrize(
    "params",
    [
        {"lat": 91},
        {"lon": -181},
        {"date": "2026-13-01"},
        {"convention": "vedic"},
        {"ayanamsa": "raman"},
    ],
)
def test_invalid_parameters_are_problems(client: TestClient, params: dict[str, Any]) -> None:
    r = client.get("/v1/day", params=params)
    assert r.status_code == 422 and r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["status"] == 422 and body["title"] == "Invalid request" and body["errors"]
    assert body["instance"] == "/v1/day"


def test_unknown_timezone_and_polar_day(client: TestClient) -> None:
    r = client.get("/v1/day", params={"tz": "Mars/Olympus"})
    assert r.status_code == 422 and r.json()["type"] == "urn:hora-api:problem:unknown-timezone"
    polar = client.get("/v1/day", params={"date": "2026-06-21", "lat": 85, "lon": 0, "tz": "UTC"})
    assert polar.status_code == 422 and polar.json()["type"] == "urn:hora-api:problem:no-sun-event"
    assert polar.headers["content-type"] == "application/problem+json"


def test_unknown_route_is_problem(client: TestClient) -> None:
    r = client.get("/v1/nope")
    assert r.status_code == 404 and r.headers["content-type"] == "application/problem+json"
    assert r.json()["title"] == "Not Found"


# ---------------------------------------------------------------------------
# /v1/horas/personal
# ---------------------------------------------------------------------------


def by_start(j: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {hhmm(h["start"]): h for h in j["horas"]}


def test_golden_personal_via_stored_profile(client: TestClient) -> None:
    r = client.get("/v1/horas/personal", params={**PJ, "profile_id": "golden"})
    assert r.status_code == 200
    j = r.json()
    assert j["profile"] == {"id": "golden", "display_name": "Golden (fixture)"}
    s = by_start(j)
    assert [round(s[k]["score"]) for k in ("07:02", "16:02", "20:02", "21:02")] == [
        58,
        100,
        100,
        83,
    ]
    for blocked in ("09:02", "13:02"):
        assert s[blocked]["score"] is None and s[blocked]["clean_parts"] == []
        assert s[blocked]["blocked_reasons"]
    assert s["10:02"]["tara_change"]["before"]["name"] == "Mitra"
    assert s["10:02"]["tara_change"]["after"]["name"] == "Parama Mitra"
    assert (
        s["15:02"]["chandra_change"]["before"]["house"],
        s["15:02"]["chandra_change"]["after"]["house"],
    ) == (12, 1)
    assert s["07:02"]["components"] == {"tara": 25.0, "chandra": 0.0, "hora": 33.3, "dasha": None}
    assert j["unverified_tables"] == ["durmuhurta", "functional", "varjyam"]


def test_top_windows(client: TestClient) -> None:
    top = client.get("/v1/horas/personal", params={**PJ, "profile_id": "golden"}).json()["top"]
    overall, morning, night = top["best_overall"], top["best_before_noon"], top["best_after_sunset"]
    assert (overall["lord"], overall["score"], hhmm(overall["start"])) == ("Saturn", 100.0, "16:02")
    assert (morning["lord"], round(morning["score"]), hhmm(morning["start"])) == (
        "Mercury",
        58,
        "07:02",
    )
    assert (night["lord"], night["score"], hhmm(night["start"])) == ("Venus", 100.0, "20:02")
    assert datetime.fromisoformat(morning["start"]).hour < 12
    assert datetime.fromisoformat(night["start"]) >= datetime.fromisoformat(
        client.get("/v1/day", params=PJ).json()["sun"]["sunset"]
    )


def test_post_inline_profile_matches_stored(client: TestClient) -> None:
    stored = client.get("/v1/horas/personal", params={**PJ, "profile_id": "golden"}).json()
    posted = client.post("/v1/horas/personal", params=PJ, json=GOLDEN_PROFILE)
    assert posted.status_code == 200 and posted.json() == stored
    by_index = {**GOLDEN_PROFILE, "janma_nakshatra": 3, "janma_rasi": 1, "lagna": 10}
    assert client.post("/v1/horas/personal", params=PJ, json=by_index).json() == stored


def test_post_invalid_profile(client: TestClient) -> None:
    r = client.post("/v1/horas/personal", params=PJ, json={**GOLDEN_PROFILE, "lagna": "Nowhere"})
    assert r.status_code == 422 and r.headers["content-type"] == "application/problem+json"
    assert any("lagna" in e["loc"] for e in r.json()["errors"])


def test_unknown_profile(client: TestClient) -> None:
    r = client.get("/v1/horas/personal", params={**PJ, "profile_id": "nobody"})
    assert r.status_code == 404 and r.json()["type"] == "urn:hora-api:problem:profile-not-found"
    missing = client.get("/v1/horas/personal", params=PJ)
    assert missing.status_code == 422


# ---------------------------------------------------------------------------
# /v1/horas/rasi, /v1/profiles
# ---------------------------------------------------------------------------


def test_rasi_matrix(client: TestClient) -> None:
    j = client.get("/v1/horas/rasi", params=PJ).json()
    assert len(j["rasis"]) == 12 and len(j["horas"]) == 24
    assert all(len(r["cells"]) == 24 for r in j["rasis"])
    assert [r["name"] for r in j["rasis"]][:2] == ["Mesha", "Vrishabha"]
    kanya, tula = j["rasis"][5], j["rasis"][6]
    assert sum("chandrashtama" in c["blocked_reasons"] for c in kanya["cells"]) == 9
    assert sum("chandrashtama" in c["blocked_reasons"] for c in tula["cells"]) == 16
    assert j["horas"][0]["start"].endswith("+08:00")
    assert j["unverified_tables"] == ["durmuhurta", "varjyam"]


def test_profiles_list_never_leaks_birth_data(client: TestClient) -> None:
    r = client.get("/v1/profiles")
    assert r.json() == {"profiles": [{"id": "golden", "display_name": "Golden (fixture)"}]}
    assert "birth_note" not in r.text and "janma" not in r.text and "lagna" not in r.text


def test_profiles_file_changes_are_picked_up(tmp_path: Path) -> None:
    with make_client(tmp_path) as c:
        assert len(c.get("/v1/profiles").json()["profiles"]) == 1
        path = tmp_path / "profiles.yaml"
        path.write_text(
            yaml.safe_dump({"profiles": [GOLDEN_PROFILE, {**GOLDEN_PROFILE, "id": "b"}]})
        )
        import os

        os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))
        assert [p["id"] for p in c.get("/v1/profiles").json()["profiles"]] == ["golden", "b"]


# ---------------------------------------------------------------------------
# Health, auth, cache, OpenAPI
# ---------------------------------------------------------------------------


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready", "profiles": 1}


def test_ready_with_missing_profiles_file_is_empty_store(tmp_path: Path) -> None:
    with make_client(tmp_path, profiles_path=tmp_path / "absent.yaml") as c:
        assert c.get("/readyz").json() == {"status": "ready", "profiles": 0}
        assert c.get("/v1/profiles").json() == {"profiles": []}


def test_ready_fails_on_broken_profiles_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("profiles: [ {id: x}\n")
    with make_client(tmp_path, profiles_path=bad) as c:
        r = c.get("/readyz")
        assert r.status_code == 503 and r.headers["content-type"] == "application/problem+json"
        assert c.get("/v1/profiles").status_code == 503
        assert c.get("/healthz").status_code == 200


def test_api_key_auth(tmp_path: Path) -> None:
    with make_client(tmp_path, api_keys="alpha, beta") as c:
        r = c.get("/v1/day", params=PJ)
        assert r.status_code == 401 and r.headers["content-type"] == "application/problem+json"
        assert r.headers["www-authenticate"] == "ApiKey"
        assert r.json()["type"] == "urn:hora-api:problem:unauthorized"
        assert c.get("/v1/day", params=PJ, headers={"X-API-Key": "nope"}).status_code == 401
        for key in ("alpha", "beta"):
            assert c.get("/v1/day", params=PJ, headers={"X-API-Key": key}).status_code == 200
        assert c.get("/v1/profiles").status_code == 401
        assert c.get("/healthz").status_code == 200 and c.get("/readyz").status_code == 200


def test_auth_is_off_by_default(client: TestClient) -> None:
    assert client.get("/v1/profiles").status_code == 200


def test_days_are_cached(tmp_path: Path) -> None:
    with make_client(tmp_path) as c:
        cache = c.app.state.services.cache  # type: ignore[attr-defined]
        assert isinstance(c.app.state.services, Services)  # type: ignore[attr-defined]
        c.get("/v1/day", params=PJ)
        assert (cache.hits, cache.misses) == (0, 1)
        c.get("/v1/day", params=PJ)
        c.get("/v1/horas/rasi", params=PJ)
        c.get("/v1/horas/personal", params={**PJ, "profile_id": "golden"})
        assert (cache.hits, cache.misses) == (3, 1)
        c.get("/v1/day", params={**PJ, "convention": "classical"})
        c.get("/v1/day", params={**PJ, "ayanamsa": "kp"})
        assert cache.misses == 3


def test_cache_evicts_least_recently_used(tmp_path: Path) -> None:
    with make_client(tmp_path, cache_size=1) as c:
        cache = c.app.state.services.cache  # type: ignore[attr-defined]
        c.get("/v1/day", params=PJ)
        c.get("/v1/day", params={**PJ, "date": "2026-10-01"})
        c.get("/v1/day", params=PJ)
        assert (cache.hits, cache.misses) == (0, 3)


def test_openapi_is_published_and_valid(client: TestClient) -> None:
    r = client.get("/v1/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    validate(spec)
    assert set(spec["paths"]) == {
        "/v1/day", "/v1/horas/personal", "/v1/horas/rasi", "/v1/profiles", "/healthz", "/readyz",
        "/v1/cards/day", "/v1/cards/rasi",
    }  # fmt: skip
    assert set(spec["paths"]["/v1/horas/personal"]) == {"get", "post"}
    assert "X-API-Key" in str(spec["components"]["securitySchemes"])
