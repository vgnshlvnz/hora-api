"""Vimshottari dasha: nakshatra lords, balance at birth, antardashas, year length, properties."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hora_api.core import astro, dasha
from hora_api.core.astro import NAKSHATRA_SPAN
from hora_api.data.loader import load_tables

TABLE = load_tables().dasha
BIRTH = datetime(2026, 3, 24, 5, 30, tzinfo=UTC)  # synthetic
YEAR = timedelta(days=365.25)
SEQUENCE = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]

# Nakshatra names grouped by the dasha they start in (the classical three-fold grouping).
LORD_OF = {
    "Ketu": ("Ashwini", "Magha", "Mula"),
    "Venus": ("Bharani", "Purva Phalguni", "Purva Ashadha"),
    "Sun": ("Krittika", "Uttara Phalguni", "Uttara Ashadha"),
    "Moon": ("Rohini", "Hasta", "Shravana"),
    "Mars": ("Mrigashira", "Chitra", "Dhanishta"),
    "Rahu": ("Ardra", "Swati", "Shatabhisha"),
    "Jupiter": ("Punarvasu", "Vishakha", "Purva Bhadrapada"),
    "Saturn": ("Pushya", "Anuradha", "Uttara Bhadrapada"),
    "Mercury": ("Ashlesha", "Jyeshtha", "Revati"),
}
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya",
    "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]  # fmt: skip


def maha(spans: list[dasha.DashaSpan]) -> list[dasha.DashaSpan]:
    return [s for s in spans if s.level == "maha"]


def antar(spans: list[dasha.DashaSpan], within: dasha.DashaSpan) -> list[dasha.DashaSpan]:
    return [s for s in spans if s.level == "antar" and within.start <= s.start < within.end]


def test_table() -> None:
    assert list(TABLE.lords) == SEQUENCE and list(TABLE.years) == YEARS
    assert sum(TABLE.years) == 120


def test_nakshatra_lords_follow_the_classical_grouping() -> None:
    for lord, names in LORD_OF.items():
        for name in names:
            assert dasha.nakshatra_lord(NAKSHATRAS.index(name), TABLE) == lord, name


def test_start_of_ashwini_gives_a_full_ketu_dasha() -> None:
    spans = dasha.vimshottari(0.0, BIRTH, TABLE)
    first = maha(spans)[0]
    assert (first.lord, first.start, first.end - first.start) == ("Ketu", BIRTH, 7 * YEAR)
    inner = antar(spans, first)
    # Antardashas run in the same order from the dasha lord; each lasts 7 * years / 120.
    assert [s.lord for s in inner] == SEQUENCE
    for s, years in zip(inner, YEARS, strict=True):
        expected = timedelta(days=7 * years / 120 * 365.25)
        assert abs((s.end - s.start) - expected) < timedelta(seconds=1)
    assert inner[0].start == BIRTH and inner[-1].end == first.end
    assert [m.lord for m in maha(spans)][:3] == ["Ketu", "Venus", "Sun"]


def test_balance_at_birth_is_the_unused_part_of_the_first_dasha() -> None:
    quarter = NAKSHATRA_SPAN / 4  # a quarter of the way through Ashwini: 3/4 of 7 years remain
    first = maha(dasha.vimshottari(quarter, BIRTH, TABLE))[0]
    assert first.lord == "Ketu" and first.start == BIRTH
    assert abs((first.end - BIRTH) - 0.75 * 7 * YEAR) < timedelta(seconds=1)
    mid = maha(dasha.vimshottari(NAKSHATRA_SPAN / 2, BIRTH, TABLE))[0]
    assert abs((mid.end - BIRTH) - 3.5 * YEAR) < timedelta(seconds=1)
    # Just into Bharani (nakshatra 1): Venus, almost all of its 20 years.
    bharani = maha(dasha.vimshottari(NAKSHATRA_SPAN + 1e-9, BIRTH, TABLE))[0]
    assert bharani.lord == "Venus" and abs((bharani.end - BIRTH) - 20 * YEAR) < timedelta(days=1)


def test_antardashas_that_ended_before_birth_are_left_out_and_the_rest_clipped() -> None:
    """Moon 3.7 degrees into Rohini (a Moon dasha, 27.8% used): worked by hand.

    The Moon dasha nominally began 10 * 0.278 = 2.78 years before birth. Its antardashas last
    Moon 0.833, Mars 0.583, Rahu 1.5, ... years, so Moon and Mars ended before birth
    (cumulative 1.417 years) and Rahu ends at 2.917 - 2.78 = 0.136 years after birth.
    """
    longitude = 3 * NAKSHATRA_SPAN + 3.7074
    spans = dasha.vimshottari(longitude, BIRTH, TABLE)
    first = maha(spans)[0]
    assert first.lord == "Moon" and first.start == BIRTH
    frac = 3.7074 / NAKSHATRA_SPAN
    assert abs((first.end - BIRTH) - 10 * (1 - frac) * YEAR) < timedelta(seconds=1)
    inner = antar(spans, first)
    assert [s.lord for s in inner][:3] == ["Rahu", "Jupiter", "Saturn"]  # Moon, Mars dropped
    nominal_start = BIRTH - 10 * frac * YEAR
    rahu_end = nominal_start + timedelta(days=(10 * 10 + 10 * 7 + 10 * 18) / 120 * 365.25)
    assert inner[0].start == BIRTH and abs(inner[0].end - rahu_end) < timedelta(seconds=1)
    assert inner[-1].end == first.end


def test_year_length_is_a_parameter() -> None:
    savana = maha(dasha.vimshottari(0.0, BIRTH, TABLE, year_days=360.0))[0]
    assert savana.end - savana.start == timedelta(days=7 * 360)
    with pytest.raises(ValueError, match="positive"):
        dasha.vimshottari(0.0, BIRTH, TABLE, year_days=0)


def test_naive_birth_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        dasha.vimshottari(0.0, datetime(2026, 3, 24, 5, 30), TABLE)


def test_running_returns_the_dasha_and_its_bhukti() -> None:
    spans = dasha.vimshottari(0.0, BIRTH, TABLE)
    now = dasha.running(spans, BIRTH + timedelta(days=200))
    assert [(s.level, s.lord) for s in now] == [("maha", "Ketu"), ("antar", "Venus")]
    assert dasha.running(spans, BIRTH - timedelta(days=1)) == []


def test_first_dasha_lord_matches_the_moon_nakshatra() -> None:
    """The Moon position comes from core.astro; the golden birth is in Rohini."""
    moon = astro.moon_state(BIRTH)
    spans = dasha.vimshottari(moon.longitude, BIRTH, TABLE)
    assert dasha.nakshatra_lord(moon.nakshatra, TABLE) == maha(spans)[0].lord


longitudes = st.floats(min_value=0.0, max_value=360.0, exclude_max=True, allow_nan=False)
births = st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2035, 1, 1))
year_lengths = st.sampled_from([360.0, 365.25, 365.2425])


@settings(max_examples=60, deadline=None)
@given(lon=longitudes, birth=births, year_days=year_lengths)
def test_periods_tile_time_and_follow_the_sequence(
    lon: float, birth: datetime, year_days: float
) -> None:
    birth = birth.replace(tzinfo=UTC)
    spans = dasha.vimshottari(lon, birth, TABLE, year_days=year_days)
    mahas = maha(spans)
    assert mahas[0].start == birth
    assert all(a.end == b.start for a, b in zip(mahas, mahas[1:], strict=False))
    # Lords follow the cycle. A Moon exactly on a nakshatra boundary can leave the previous
    # dasha with a balance too small to list (under a microsecond), so the first may be the next.
    first = int(lon // NAKSHATRA_SPAN) % 9
    start = SEQUENCE.index(mahas[0].lord)
    assert start in (first, (first + 1) % 9)
    assert [m.lord for m in mahas] == [SEQUENCE[(start + k) % 9] for k in range(len(mahas))]
    # Every full dasha lasts exactly its years.
    for m in mahas[1:-1]:
        expected = timedelta(days=YEARS[SEQUENCE.index(m.lord)] * year_days)
        assert abs((m.end - m.start) - expected) < timedelta(seconds=1)
    for m in mahas:
        inner = antar(spans, m)
        assert len(inner) <= 9 and inner[0].start == m.start and inner[-1].end == m.end
        assert all(a.end == b.start for a, b in zip(inner, inner[1:], strict=False))
        if m is not mahas[0]:
            assert len(inner) == 9 and [s.lord for s in inner][0] == m.lord
    assert mahas[-1].end >= birth + timedelta(days=120 * year_days)
