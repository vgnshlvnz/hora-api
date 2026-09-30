"""Checks against Drik Panchang for Kuala Lumpur, Friday 2026-10-30.

The values below were read from that Drik Panchang day page and supplied by the project owner
(the place is inferred: Drik's sunrise 06:57 matches Kuala Lumpur). Drik rounds to the minute, so
tolerances are 1-2 minutes. Sunset differs by 2 minutes (Drik 18:58, disc-centre calculation
18:56), a horizon convention, and does not affect the checks that matter here.

    Sunrise 06:57   Sunset 18:58   Krishna Paksha   Weekday Friday   Moon sign Mithuna
    Tithi Panchami (Krishna, tithi 20) upto 21:54
    Nakshatram Mrigashirisham upto 11:34, then Ardra
    Rahu Kalam 11:27-12:57   Gulikai 08:27-09:57   Yamaganda 15:57-17:27
    Dur Muhurtam 09:21-10:09 and 13:21-14:09     Varjyam 19:19-20:47
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from hora_api.core import astro
from hora_api.core import day as D
from hora_api.data.loader import load_tables

KL = ZoneInfo("Asia/Kuala_Lumpur")
TABLES = load_tables()
DAY = D.make_day(date(2026, 10, 30), KL, 3.139, 101.6869)
FRIDAY = 5
MRIGASHIRA, ARDRA = 4, 5


def minutes_off(t: datetime, hh: int, mm: int) -> float:
    local = t.astimezone(KL)
    return (
        abs((local - local.replace(hour=hh, minute=mm, second=0, microsecond=0)).total_seconds())
        / 60
    )


def test_astronomy_matches_drik() -> None:
    assert DAY.weekday == FRIDAY
    assert minutes_off(DAY.sunrise, 6, 57) <= 1
    changes = [t for t in astro.transitions(DAY.sunrise, DAY.next_sunrise) if t.kind != "rasi"]
    nak = next(t for t in changes if t.kind == "nakshatra")
    tithi = next(t for t in changes if t.kind == "tithi")
    assert (nak.from_index, nak.to_index) == (MRIGASHIRA, ARDRA) and minutes_off(
        nak.time, 11, 34
    ) <= 1
    assert (tithi.from_index, tithi.to_index) == (20, 21) and minutes_off(tithi.time, 21, 54) <= 2
    assert astro.moon_state(DAY.sunrise).rasi == 2  # Mithuna
    assert astro.paksha(DAY.sunrise) == "krishna"


def test_kalams_match_drik() -> None:
    k = D.kalams(DAY, TABLES)
    for window, (h1, m1, h2, m2) in (
        (k.rahu_kalam, (11, 27, 12, 57)),
        (k.gulika_kalam, (8, 27, 9, 57)),
        (k.yamagandam, (15, 57, 17, 27)),
    ):
        assert minutes_off(window.start, h1, m1) <= 1 and minutes_off(window.end, h2, m2) <= 1


def test_friday_durmuhurta_matches_drik() -> None:
    windows = D.durmuhurta(DAY, TABLES)
    assert len(windows) == 2  # Drik lists two, both in the day; no night one
    (a, b) = windows
    assert minutes_off(a.start, 9, 21) <= 1 and minutes_off(a.end, 10, 9) <= 1
    assert minutes_off(b.start, 13, 21) <= 1 and minutes_off(b.end, 14, 9) <= 1


def test_ardra_varjyam_matches_drik() -> None:
    """Ardra starts its varjyam 21 ghatikas in (not the 11 first recalled): 19:19-20:47."""
    assert TABLES.varjyam.start_ghati[ARDRA] == 21
    windows = D.varjyam(DAY, TABLES)
    assert len(windows) == 1
    assert minutes_off(windows[0].start, 19, 19) <= 1 and minutes_off(windows[0].end, 20, 47) <= 1


def test_only_the_checked_rows_are_marked_verified() -> None:
    unverified = TABLES.unverified
    assert "varjyam:Ardra" not in unverified and "varjyam:Ashwini" in unverified
    assert len([u for u in unverified if u.startswith("varjyam:")]) == 26
    assert "durmuhurta:friday" not in unverified and "durmuhurta:monday" in unverified
    # The table-level flags stay while any row is unchecked.
    assert {"varjyam", "durmuhurta", "gowri"} <= unverified
