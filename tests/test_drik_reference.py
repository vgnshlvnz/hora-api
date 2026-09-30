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

from datetime import date, datetime, timedelta
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


# Drik Panchang, Kuala Lumpur, read on the 28 days from 2026-11-01. Dur Muhurtam windows per date
# (HH:MM pairs, local time; a night window may end after midnight).
DRIK_DURMUHURTA = {
    date(2026, 11, 1): [("17:21", "18:09")],  # Sunday
    date(2026, 11, 2): [("13:21", "14:09"), ("15:45", "16:33")],  # Monday
    date(2026, 11, 3): [("09:21", "10:09"), ("23:45", "00:33")],  # Tuesday, day and night
    date(2026, 11, 4): [("12:33", "13:21")],  # Wednesday
    date(2026, 11, 5): [("10:57", "11:45"), ("15:45", "16:33")],  # Thursday
    date(2026, 11, 7): [("06:57", "07:45"), ("07:45", "08:33")],  # Saturday
}

# Varjyam windows by nakshatra index (Drik date, start, end). Only windows that start inside the
# Drik day; each is 4 ghatikas of its nakshatra.
DRIK_VARJYAM = {
    0: (date(2026, 11, 22), "03:02", "04:31"),
    1: (date(2026, 11, 23), "15:28", "16:55"),
    2: (date(2026, 11, 24), "15:13", "16:39"),
    3: (date(2026, 11, 25), "16:02", "17:27"),
    4: (date(2026, 11, 25), "04:02", "05:27"),  # Nov 26 early morning, shown on Nov 25
    5: (date(2026, 11, 26), "03:45", "05:11"),
    6: (date(2026, 11, 27), "04:29", "05:56"),
    7: (date(2026, 11, 1), "15:46", "17:18"),
    8: (date(2026, 11, 2), "19:25", "20:58"),
    9: (date(2026, 11, 3), "18:06", "19:41"),
    10: (date(2026, 11, 4), "13:57", "15:34"),
    11: (date(2026, 11, 5), "13:19", "14:57"),
    12: (date(2026, 11, 6), "15:06", "16:45"),  # Hasta: 21 ghatikas, not the 22 first recalled
    13: (date(2026, 11, 7), "15:36", "17:17"),
    14: (date(2026, 11, 8), "14:19", "16:02"),
    15: (date(2026, 11, 9), "15:57", "17:40"),
    16: (date(2026, 11, 10), "16:12", "17:57"),
    17: (date(2026, 11, 11), "20:21", "22:08"),
    18: (date(2026, 11, 12), "01:48", "03:36"),  # Nov 13 early morning; see the Mula note below
    19: (date(2026, 11, 13), "06:38", "08:26"),  # Nov 14 early morning
    20: (date(2026, 11, 15), "07:55", "09:44"),
    21: (date(2026, 11, 15), "06:26", "08:14"),  # Nov 16 early morning
    22: (date(2026, 11, 17), "09:09", "10:55"),
    23: (date(2026, 11, 18), "14:45", "16:27"),
    24: (date(2026, 11, 19), "15:16", "16:55"),
    25: (date(2026, 11, 20), "19:00", "20:35"),
    26: (date(2026, 11, 21), "20:52", "22:25"),
}


def _at(d: date, hhmm: str, after: datetime | None = None) -> datetime:
    hh, mm = (int(x) for x in hhmm.split(":"))
    t = datetime(d.year, d.month, d.day, hh, mm, tzinfo=KL)
    return t + timedelta(days=1) if after is not None and t <= after else t


def test_durmuhurta_all_weekdays_match_drik() -> None:
    for d, expected in DRIK_DURMUHURTA.items():
        day = D.make_day(d, KL, 3.139, 101.6869)
        windows = D.durmuhurta(day, TABLES)
        assert len(windows) == len(expected), d
        for w, (a, b) in zip(windows, expected, strict=True):
            start = _at(d, a)
            end = _at(d, b, after=start)
            assert abs((w.start - start).total_seconds()) <= 120, (d, a)
            assert abs((w.end - end).total_seconds()) <= 120, (d, b)


def test_varjyam_values_match_drik() -> None:
    """Every nakshatra's varjyam window, computed from the table, lands on Drik's window."""
    for index, (d, a, b) in DRIK_VARJYAM.items():
        day = D.make_day(d, KL, 3.139, 101.6869)
        start = _at(d, a)
        if start < day.sunrise:  # listed on this Drik day but after midnight
            start += timedelta(days=1)
        end = min(_at(start.date(), b, after=start), day.next_sunrise)  # the code clips to the day
        windows = [
            w for w in D.varjyam(day, TABLES) if abs((w.start - start).total_seconds()) < 3600
        ]
        assert len(windows) == 1, (index, d)
        assert abs((windows[0].start - start).total_seconds()) <= 120, (index, d)
        assert abs((windows[0].end - end).total_seconds()) <= 120, (index, d)


def test_only_the_checked_rows_are_marked_verified() -> None:
    unverified = TABLES.unverified
    # Every varjyam row is checked except Mula: Drik also lists a second window (56 ghatikas,
    # 17:59-19:47 on 2026-11-13) that the one-window-per-nakshatra table cannot express.
    assert {u for u in unverified if u.startswith("varjyam:")} == {"varjyam:Mula"}
    assert not {u for u in unverified if u.startswith("durmuhurta")}
    # Table-level flags stay while any row is unchecked.
    assert {"varjyam", "gowri"} <= unverified and "durmuhurta" not in unverified


# Drik Panchang Gowri Panchangam (Nalla Neram), Kuala Lumpur, 2026-11-01 (Sunday) to 2026-11-07
# (Saturday): (day sequence, night sequence). The 8th Saturday night segment is omitted: Drik
# printed Soram twice there and no Rogam, so the table's Rogam is an inference.
DRIK_GOWRI = {
    date(2026, 11, 1): (
        "Uthi Amirdha Rogam Laabam Dhanam Sugam Soram Visham",
        "Dhanam Sugam Soram Visham Uthi Amirdha Rogam Laabam",
    ),
    date(2026, 11, 2): (
        "Amirdha Visham Rogam Laabam Dhanam Sugam Soram Uthi",
        "Sugam Soram Uthi Amirdha Visham Rogam Laabam Dhanam",
    ),
    date(2026, 11, 3): (
        "Rogam Laabam Dhanam Sugam Soram Uthi Visham Amirdha",
        "Soram Uthi Visham Amirdha Rogam Laabam Dhanam Sugam",
    ),
    date(2026, 11, 4): (
        "Laabam Dhanam Sugam Soram Visham Uthi Amirdha Rogam",
        "Uthi Amirdha Rogam Laabam Dhanam Sugam Soram Visham",
    ),
    date(2026, 11, 5): (
        "Dhanam Sugam Soram Uthi Amirdha Visham Rogam Laabam",
        "Amirdha Visham Rogam Laabam Dhanam Sugam Soram Uthi",
    ),
    date(2026, 11, 6): (
        "Sugam Soram Uthi Visham Amirdha Rogam Laabam Dhanam",
        "Rogam Laabam Dhanam Sugam Soram Uthi Visham Amirdha",
    ),
    date(2026, 11, 7): (
        "Soram Uthi Visham Amirdha Rogam Laabam Dhanam Sugam",
        "Laabam Dhanam Sugam Soram Uthi Visham Amirdha",  # first 7 only
    ),
}


def test_gowri_sequences_and_times_match_drik() -> None:
    for d, (day_names, night_names) in DRIK_GOWRI.items():
        day = D.make_day(d, KL, 3.139, 101.6869)
        segs = D.gowri(day, TABLES)
        day_segs = [g for g in segs if not g.is_night]
        night_segs = [g for g in segs if g.is_night]
        assert [g.name for g in day_segs] == day_names.split(), d
        assert [g.name for g in night_segs][: len(night_names.split())] == night_names.split(), d
        # 90-minute segments from sunrise (06:57) and from sunset (18:57).
        assert (
            minutes_off(day_segs[0].start, 6, 57) <= 2 and minutes_off(day_segs[7].end, 18, 57) <= 2
        )
        assert minutes_off(night_segs[0].start, 18, 57) <= 2
        assert abs((day_segs[0].end - day_segs[0].start).total_seconds() / 60 - 90) <= 2


def test_uthi_is_good_as_in_drik() -> None:
    assert TABLES.gowri.nature["Uthi"] == "good"
    assert {n for n, v in TABLES.gowri.nature.items() if v == "bad"} == {"Rogam", "Soram", "Visham"}
    assert "gowri:saturday" in TABLES.unverified and "gowri:sunday" not in TABLES.unverified
