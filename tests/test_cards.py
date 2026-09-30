"""chat-cards tests: the golden PJ day (Wed 2026-09-30) as client-neutral cards."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi.testclient import TestClient

from hora_api.api.app import create_app
from hora_api.api.cards import _Clock, _span_words
from hora_api.api.settings import ApiSettings
from hora_api.core.day import Day, MoonSpan

PJ: dict[str, Any] = {
    "date": "2026-09-30", "lat": 3.107, "lon": 101.606, "tz": "Asia/Kuala_Lumpur",
}  # fmt: skip


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = ApiSettings(profiles_path=tmp_path / "none.yaml")
    with TestClient(create_app(settings)) as c:
        yield c


def rows(card: dict[str, Any], section: str) -> list[tuple[str, str, str]]:
    sec = next(s for s in card["sections"] if s["id"] == section)
    return [(r["label"], r["value"], r["tone"]) for r in sec["rows"]]


def test_golden_day_card(client: TestClient) -> None:
    r = client.get("/v1/cards/day", params=PJ)
    assert r.status_code == 200 and r.headers["content-type"] == "application/json"
    card = r.json()
    assert card["kind"] == "day" and card["title"] == "Wednesday 30 Sep 2026"
    assert card["subtitle"] == "Asia/Kuala_Lumpur · 3.107, 101.606 · tamil · lahiri"
    assert [s["id"] for s in card["sections"]] == ["sun", "moon", "avoid", "nalla_neram", "horas"]

    assert rows(card, "sun") == [
        ("Sunrise", "07:02", "neutral"), ("Sunset", "19:05", "neutral"),
        ("Next sunrise", "07:02+1", "neutral"),
    ]  # fmt: skip
    # Verified ephemeris times (the brief said ~10:17, ~15:47, ~17:32).
    assert rows(card, "moon") == [
        ("Nakshatra", "Bharani → Krittika (10:07)", "neutral"),
        ("Rasi", "Mesha → Vrishabha (15:44)", "neutral"),
        ("Tithi", "19 → 20 (17:26)", "neutral"),
    ]
    avoid = {label: value for label, value, _ in rows(card, "avoid")}
    assert avoid["Yamagandam"] == "08:32–10:03"
    assert avoid["Gulika kalam"] == "11:33–13:04"
    assert avoid["Rahu kalam"] == "13:04–14:34"
    assert set(avoid) == {"Yamagandam", "Gulika kalam", "Rahu kalam", "Durmuhurta", "Varjyam"}
    assert avoid["Varjyam"] == "21:20–22:50"
    assert all(tone == "bad" for _, _, tone in rows(card, "avoid"))
    starts = [v.split("–")[0] for _, v, _ in rows(card, "avoid")]
    assert starts == sorted(starts)  # chronological


def test_horas_and_gowri_sections(client: TestClient) -> None:
    card = client.get("/v1/cards/day", params=PJ).json()
    horas = rows(card, "horas")
    assert len(horas) == 24 and card["sections"][-1]["title"] == "Horas (tamil)"
    assert horas[:3] == [
        ("07:02–08:02", "Mercury", "neutral"),
        ("08:02–09:02", "Moon", "neutral"),
        ("09:02–10:02", "Saturn", "neutral"),
    ]
    assert horas[-1][:2] == ("06:02+1–07:02+1", "Saturn")
    nalla = rows(card, "nalla_neram")
    assert nalla and all(tone == "good" for _, _, tone in nalla)  # good segments only
    assert nalla[0] == ("Laabam", "07:02–08:32", "good")  # Wednesday day row (unverified table)
    assert any("+1" in value for _, value, _ in nalla)  # night segments after midnight


def test_unverified_tables_are_flagged(client: TestClient) -> None:
    card = client.get("/v1/cards/day", params=PJ).json()
    assert card["unverified_tables"] == ["durmuhurta", "gowri", "varjyam"]
    assert card["footer"] == "Unverified tables in use: durmuhurta, gowri, varjyam."


def test_cards_use_request_timezone_and_options(client: TestClient) -> None:
    ist = client.get("/v1/cards/day", params={**PJ, "tz": "Asia/Kolkata"}).json()
    assert ist["subtitle"].startswith("Asia/Kolkata")
    assert rows(ist, "sun")[0] == ("Sunrise", "04:32", "neutral")  # same sunrise, IST clock
    classical = client.get("/v1/cards/day", params={**PJ, "convention": "classical"}).json()
    assert classical["subtitle"].endswith("classical · lahiri")
    tamil_horas = rows(client.get("/v1/cards/day", params=PJ).json(), "horas")
    assert rows(classical, "horas") != tamil_horas  # day/12 slots are not 60 minutes
    kp = client.get("/v1/cards/day", params={**PJ, "ayanamsa": "kp"}).json()
    assert kp["subtitle"].endswith("tamil · kp")


def test_golden_rasi_card(client: TestClient) -> None:
    card = client.get("/v1/cards/rasi", params=PJ).json()
    assert card["kind"] == "rasi" and card["title"] == "Rasis · Wednesday 30 Sep 2026"
    assert [s["id"] for s in card["sections"]] == ["chandrashtama", "best", "all"]
    # Moon in Mesha until ~15:44 is 8th from Kanya; in Vrishabha after it is 8th from Tula.
    assert rows(card, "chandrashtama") == [
        ("Kanya", "until 15:44", "bad"),
        ("Tula", "from 15:44", "bad"),
    ]
    assert rows(card, "best") == [
        ("Karka", "100% · 74.9% of the day clean", "good"),
        ("Vrischika", "100% · 74.9% of the day clean", "good"),
        ("Tula", "100% · 17.4% of the day clean", "good"),
    ]
    everything = rows(card, "all")
    assert [label for label, _, _ in everything][:3] == ["Mesha", "Vrishabha", "Mithuna"]
    assert len(everything) == 12 and everything[-1][0] == "Meena"
    assert everything[5] == ("Kanya", "50% · 57.5% of the day clean", "neutral")
    assert card["unverified_tables"] == ["durmuhurta", "varjyam"]
    assert card["footer"] == "Unverified tables in use: durmuhurta, varjyam."


def test_span_words_and_clock() -> None:
    kl = ZoneInfo("Asia/Kuala_Lumpur")
    sunrise = datetime(2026, 9, 29, 23, 0, tzinfo=UTC)  # 07:00 KL on the 30th
    day = Day(
        date_local=date(2026, 9, 30), weekday=3, sunrise=sunrise,
        sunset=sunrise + timedelta(hours=12), next_sunrise=sunrise + timedelta(hours=24),
        nakshatra_spans=(), rasi_spans=(MoonSpan(0, sunrise, sunrise + timedelta(hours=24)),),
    )  # fmt: skip
    clock = _Clock(kl, date(2026, 9, 30))
    h = timedelta(hours=1)
    assert _span_words(sunrise, day.next_sunrise, day, clock) == "all day"
    assert _span_words(sunrise, sunrise + 5 * h, day, clock) == "until 12:00"
    assert _span_words(sunrise + 5 * h, day.next_sunrise, day, clock) == "from 12:00"
    assert _span_words(sunrise + 2 * h, sunrise + 5 * h, day, clock) == "09:00–12:00"
    assert clock.at(sunrise + 18 * h) == "01:00+1"  # 07:00 + 18 h is 01:00 the next day
    assert clock.at(sunrise + timedelta(seconds=29)) == "07:00"  # rounds to the nearest minute
    assert clock.at(sunrise + timedelta(seconds=31)) == "07:01"


def test_card_errors_and_auth(tmp_path: Path) -> None:
    open_client = TestClient(create_app(ApiSettings(profiles_path=tmp_path / "none.yaml")))
    bad = open_client.get("/v1/cards/day", params={"lat": 91})
    assert bad.status_code == 422 and bad.headers["content-type"] == "application/problem+json"
    assert open_client.get("/v1/cards/rasi", params={"tz": "Mars/X"}).status_code == 422

    locked = TestClient(create_app(ApiSettings(profiles_path=tmp_path / "none.yaml", api_keys="k")))
    for path in ("/v1/cards/day", "/v1/cards/rasi"):
        assert locked.get(path, params=PJ).status_code == 401
        assert locked.get(path, params=PJ, headers={"X-API-Key": "k"}).status_code == 200


def test_cards_share_the_day_cache(client: TestClient) -> None:
    cache = client.app.state.services.cache  # type: ignore[attr-defined]
    client.get("/v1/day", params=PJ)
    client.get("/v1/cards/day", params=PJ)
    client.get("/v1/cards/rasi", params=PJ)
    assert (cache.hits, cache.misses) == (2, 1)


# ---------------------------------------------------------------------------
# Personal card
# ---------------------------------------------------------------------------

GOLDEN_PROFILE: dict[str, Any] = yaml.safe_load(
    (Path(__file__).parent / "fixtures" / "golden.yaml").read_text()
)["profile"]


@pytest.fixture
def personal_client(tmp_path: Path) -> Iterator[TestClient]:
    profiles = tmp_path / "profiles.yaml"
    kanya = {**GOLDEN_PROFILE, "id": "kanya", "display_name": "Kanya", "janma_rasi": "Kanya"}
    profiles.write_text(yaml.safe_dump({"profiles": [GOLDEN_PROFILE, kanya]}))
    with TestClient(create_app(ApiSettings(profiles_path=profiles))) as c:
        yield c


def test_golden_personal_card(personal_client: TestClient) -> None:
    r = personal_client.get("/v1/cards/personal", params={**PJ, "profile_id": "golden"})
    assert r.status_code == 200
    card = r.json()
    assert card["kind"] == "personal"
    assert card["title"] == "Golden (fixture) · Wednesday 30 Sep 2026"
    assert card["subtitle"] == "Asia/Kuala_Lumpur · 3.107, 101.606 · tamil · lahiri"
    assert [s["id"] for s in card["sections"]] == ["top", "blocked", "tara_chandra"]

    assert rows(card, "top") == [
        ("Best overall", "16:02–17:02 Saturn (100)", "good"),
        ("Best before noon", "07:02–08:02 Mercury (58.3)", "good"),
        ("Best after sunset", "20:02–21:02 Venus (100)", "good"),
    ]
    assert rows(card, "blocked") == [
        ("09:02–10:02", "Saturn — Yamagandam", "bad"),
        ("12:02–13:02", "Sun — Durmuhurta, Gulika kalam", "bad"),
        ("13:02–14:02", "Venus — Durmuhurta, Gulika kalam, Rahu kalam", "bad"),
    ]
    # Verified ephemeris times (the brief said ~10:17 and ~15:47).
    assert rows(card, "tara_chandra") == [
        ("Tarabala until 10:07", "Mitra (8th, good)", "good"),
        ("Tarabala from 10:07", "Parama Mitra (9th, good)", "good"),
        ("Chandrabala until 15:44", "12th house (bad)", "bad"),
        ("Chandrabala from 15:44", "1st house (good)", "good"),
    ]
    assert card["unverified_tables"] == ["durmuhurta", "functional", "varjyam"]
    assert card["footer"] == "Unverified tables in use: durmuhurta, functional, varjyam."


def test_personal_card_matches_the_scored_horas(personal_client: TestClient) -> None:
    params = {**PJ, "profile_id": "golden"}
    card = personal_client.get("/v1/cards/personal", params=params).json()
    full = personal_client.get("/v1/horas/personal", params=params).json()
    top = full["top"]["best_overall"]
    assert f"{top['lord']} ({top['score']:g})" in rows(card, "top")[0][1]
    blocked_lords = [h["lord"] for h in full["horas"] if h["score"] is None]
    assert [value.split(" — ")[0] for _, value, _ in rows(card, "blocked")] == blocked_lords


def test_personal_card_shows_chandrashtama(personal_client: TestClient) -> None:
    card = personal_client.get("/v1/cards/personal", params={**PJ, "profile_id": "kanya"}).json()
    assert card["title"] == "Kanya · Wednesday 30 Sep 2026"
    # The Moon is in Mesha, 8th from Kanya, until ~15:44: nothing is left before noon.
    assert rows(card, "top")[1] == ("Best before noon", "none", "neutral")
    blocked = rows(card, "blocked")
    assert len(blocked) == 8 and all("Chandrashtama" in value for _, value, _ in blocked)
    assert rows(card, "tara_chandra")[2:] == [
        ("Chandrabala until 15:44", "8th house (Chandrashtama)", "bad"),
        ("Chandrabala from 15:44", "9th house (conditional)", "neutral"),
    ]


def test_personal_card_errors_auth_and_cache(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(yaml.safe_dump({"profiles": [GOLDEN_PROFILE]}))
    settings = ApiSettings(profiles_path=profiles, api_keys="k")
    with TestClient(create_app(settings)) as c:
        headers = {"X-API-Key": "k"}
        params = {**PJ, "profile_id": "golden"}
        assert c.get("/v1/cards/personal", params=params).status_code == 401
        missing = c.get("/v1/cards/personal", params=PJ, headers=headers)
        assert missing.status_code == 422 and missing.json()["title"] == "Invalid request"
        unknown = c.get("/v1/cards/personal", params={**PJ, "profile_id": "x"}, headers=headers)
        assert unknown.status_code == 404
        assert unknown.json()["type"] == "urn:hora-api:problem:profile-not-found"
        assert unknown.headers["content-type"] == "application/problem+json"
        assert c.get("/v1/cards/personal", params=params, headers=headers).status_code == 200
        assert c.get("/v1/cards/day", params=PJ, headers=headers).status_code == 200
        cache = c.app.state.services.cache  # type: ignore[attr-defined]
        assert cache.hits >= 1  # the day was computed once and shared
