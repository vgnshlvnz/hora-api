"""astro-core tests: golden Petaling Jaya day (Wed 2026-09-30) plus property tests."""

import ast
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import swisseph as swe
from hypothesis import given, settings
from hypothesis import strategies as st

from hora_api.core import astro
from hora_api.core.astro import Ayanamsa

KL = ZoneInfo("Asia/Kuala_Lumpur")
PJ_LAT, PJ_LON = 3.107, 101.606
DAY = date(2026, 9, 30)

# Classical names live outside core (data tables); tests only need a few.
BHARANI, KRITTIKA = 1, 2
MESHA, VRISHABHA = 0, 1


def local(t: datetime) -> datetime:
    return t.astimezone(KL)


def minutes_between(t: datetime, hh: int, mm: int) -> float:
    target = datetime(DAY.year, DAY.month, DAY.day, hh, mm, tzinfo=KL)
    return abs((t - target).total_seconds()) / 60.0


# ---------------------------------------------------------------------------
# Golden day
# ---------------------------------------------------------------------------


def test_golden_sun_events() -> None:
    ev = astro.sun_events(DAY, KL, PJ_LAT, PJ_LON)
    assert minutes_between(ev.sunrise, 7, 2) <= 1
    assert minutes_between(ev.sunset, 19, 5) <= 1
    assert (
        abs((local(ev.next_sunrise) - datetime(2026, 10, 1, 7, 2, tzinfo=KL)).total_seconds()) <= 60
    )
    for t in (ev.sunrise, ev.sunset, ev.next_sunrise):
        assert t.utcoffset() == timedelta(0)


def test_golden_transitions() -> None:
    """Sunrise to next sunrise holds exactly one nakshatra, rasi and tithi change.

    The brief quotes "about" 10:17 / 15:47 / 17:32 local. Swiss Ephemeris gives 10:07 / 15:44 /
    17:26, and an independent ephemeris (PyEphem, Lahiri ayanamsa from Swiss Ephemeris) agrees
    with those to well under a minute: the Moon is 0.100 deg short of the Krittika boundary at
    10:17 and 0.003 deg past it at 10:07. The expected values below are the verified ones.
    """
    ev = astro.sun_events(DAY, KL, PJ_LAT, PJ_LON)
    found = astro.transitions(ev.sunrise, ev.next_sunrise, Ayanamsa.LAHIRI)
    assert [(t.kind, t.from_index, t.to_index) for t in found] == [
        ("nakshatra", BHARANI, KRITTIKA),
        ("rasi", MESHA, VRISHABHA),
        ("tithi", 19, 20),
    ]
    for t, (hh, mm) in zip(found, [(10, 7), (15, 44), (17, 26)], strict=True):
        assert minutes_between(t.time, hh, mm) <= 2, (t.kind, local(t.time))


def test_golden_moon_state_at_sunrise() -> None:
    ev = astro.sun_events(DAY, KL, PJ_LAT, PJ_LON)
    state = astro.moon_state(ev.sunrise, Ayanamsa.LAHIRI)
    assert (state.nakshatra, state.pada, state.rasi) == (BHARANI, 4, MESHA)
    assert astro.tithi(ev.sunrise) == 19


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------


def test_ayanamsa_kp_differs_from_lahiri() -> None:
    t = datetime(2026, 9, 30, 0, 0, tzinfo=UTC)
    lahiri = astro.moon_state(t, Ayanamsa.LAHIRI).longitude
    kp = astro.moon_state(t, Ayanamsa.KP).longitude
    assert 0.03 < kp - lahiri < 0.2  # KP ayanamsa is a few arc-minutes smaller


def test_sidereal_mode_does_not_leak() -> None:
    t = datetime(2026, 9, 30, 0, 0, tzinfo=UTC)
    jd = t.timestamp() / 86400 + 2440587.5
    before = swe.get_ayanamsa_ut(jd)
    first = astro.moon_state(t, Ayanamsa.LAHIRI).longitude
    astro.moon_state(t, Ayanamsa.KP)
    assert astro.moon_state(t, Ayanamsa.LAHIRI).longitude == first
    assert swe.get_ayanamsa_ut(jd) == before


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        astro.moon_state(datetime(2026, 9, 30, 0, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        astro.tithi(datetime(2026, 9, 30, 0, 0))


def test_polar_day_raises() -> None:
    with pytest.raises(ValueError, match="does not rise"):
        astro.sun_events(date(2026, 6, 21), ZoneInfo("UTC"), 85.0, 0.0)


def test_end_before_start_rejected() -> None:
    t = datetime(2026, 9, 30, tzinfo=UTC)
    with pytest.raises(ValueError, match="before start"):
        astro.transitions(t, t - timedelta(hours=1))


def test_transition_times_within_30_seconds() -> None:
    start = datetime(2026, 9, 30, 0, 0, tzinfo=UTC)
    for tr in astro.transitions(start, start + timedelta(days=3)):
        after = astro.moon_state(tr.time + timedelta(seconds=1))
        before = astro.moon_state(tr.time - timedelta(seconds=30))
        if tr.kind == "nakshatra":
            assert (before.nakshatra, after.nakshatra) == (tr.from_index, tr.to_index)
        elif tr.kind == "rasi":
            assert (before.rasi, after.rasi) == (tr.from_index, tr.to_index)
        else:
            assert (
                astro.tithi(tr.time - timedelta(seconds=30)),
                astro.tithi(tr.time + timedelta(seconds=1)),
            ) == (
                tr.from_index,
                tr.to_index,
            )


def test_core_has_no_fastapi_imports() -> None:
    core = Path(astro.__file__).parent
    for path in core.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not any(n.split(".")[0] == "fastapi" for n in names), path


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

instants = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2040, 1, 1),
    timezones=st.just(UTC),
)
ayanamsas = st.sampled_from(list(Ayanamsa))


@settings(max_examples=25, deadline=None)
@given(start=instants, hours=st.integers(min_value=1, max_value=96), ayanamsa=ayanamsas)
def test_transitions_strictly_ordered(start: datetime, hours: int, ayanamsa: Ayanamsa) -> None:
    end = start + timedelta(hours=hours)
    found = astro.transitions(start, end, ayanamsa)
    keys = [(t.time, {"nakshatra": 0, "rasi": 1, "tithi": 2}[t.kind]) for t in found]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)
    assert all(start <= t.time <= end for t in found)
    for t in found:
        assert t.from_index != t.to_index


@settings(max_examples=100, deadline=None)
@given(t=instants, ayanamsa=ayanamsas)
def test_nakshatra_index_matches_longitude(t: datetime, ayanamsa: Ayanamsa) -> None:
    s = astro.moon_state(t, ayanamsa)
    assert 0.0 <= s.longitude < 360.0
    assert s.nakshatra == math.floor(s.longitude / (360 / 27))
    assert s.rasi == math.floor(s.longitude / 30)
    assert 1 <= s.pada <= 4
    assert 1 <= astro.tithi(t) <= 30


def test_paksha_follows_tithi() -> None:
    assert astro.paksha(datetime(2026, 9, 20, 0, 0, tzinfo=UTC)) == "shukla"  # tithi 9
    assert astro.paksha(datetime(2026, 9, 30, 0, 0, tzinfo=UTC)) == "krishna"  # tithi 19
    # The full moon (tithi 15 to 16) is at about 16:49 UTC on 2026-09-26.
    before = datetime(2026, 9, 26, 16, 0, tzinfo=UTC)
    after = datetime(2026, 9, 26, 17, 30, tzinfo=UTC)
    assert (astro.tithi(before), astro.paksha(before)) == (15, "shukla")
    assert (astro.tithi(after), astro.paksha(after)) == (16, "krishna")
    # The new moon (tithi 30 to 1) is at about 03:27 UTC on 2026-09-11.
    assert astro.paksha(datetime(2026, 9, 11, 2, 0, tzinfo=UTC)) == "krishna"
    assert astro.paksha(datetime(2026, 9, 11, 5, 0, tzinfo=UTC)) == "shukla"
