"""hora-engine tests: golden Petaling Jaya day (Wed 2026-09-30, tamil) plus unit checks."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from hypothesis import given, settings
from hypothesis import strategies as st

from hora_api.core import day as D
from hora_api.core.day import Day, Hora, MoonSpan
from hora_api.data.loader import load_tables

KL = ZoneInfo("Asia/Kuala_Lumpur")
TABLES = load_tables()
KANYA, VRISHABHA, MESHA = 5, 1, 0


@dataclass(frozen=True)
class Person:
    janma_rasi: int


def hhmm(t: datetime) -> str:
    """Local time rounded to the nearest minute (as panchangams print it)."""
    return (t.astimezone(KL) + timedelta(seconds=30)).strftime("%H:%M")


def near(t: datetime, hh: int, mm: int, minutes: float = 1.0) -> bool:
    local = t.astimezone(KL)
    target = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return abs((local - target).total_seconds()) <= minutes * 60


def pj_day(d: date = date(2026, 9, 30)) -> Day:
    return D.make_day(d, KL, 3.107, 101.606)


def synthetic_day(weekday_date: date = date(2026, 9, 27)) -> Day:
    """A clean 06:00-18:00 UTC day (12 h day, 12 h night); 2026-09-27 is a Sunday."""
    sunrise = datetime.combine(weekday_date, datetime.min.time(), tzinfo=UTC) + timedelta(hours=6)
    return Day(
        date_local=weekday_date,
        weekday=D.weekday_index(weekday_date),
        sunrise=sunrise,
        sunset=sunrise + timedelta(hours=12),
        next_sunrise=sunrise + timedelta(hours=24),
        nakshatra_spans=(),
        rasi_spans=(MoonSpan(0, sunrise, sunrise + timedelta(hours=24)),),
    )


# ---------------------------------------------------------------------------
# Golden PJ day
# ---------------------------------------------------------------------------


def test_golden_tamil_horas() -> None:
    horas = D.build_horas(pj_day(), "tamil", TABLES)
    assert len(horas) == 24
    expected = [
        ("07:02", "Mercury"), ("08:02", "Moon"), ("09:02", "Saturn"), ("10:02", "Jupiter"),
        ("11:02", "Mars"), ("12:02", "Sun"), ("13:02", "Venus"), ("14:02", "Mercury"),
    ]  # fmt: skip
    assert [(hhmm(h.start), h.lord) for h in horas[:8]] == expected
    assert (hhmm(horas[-1].start), horas[-1].lord) == ("06:02", "Saturn")
    for a, b in zip(horas, horas[1:], strict=False):
        assert a.end == b.start
    day = pj_day()
    assert horas[0].start == day.sunrise and horas[-1].end == day.next_sunrise
    assert horas[-1].end - horas[-1].start < timedelta(hours=1)  # 15 s short today
    assert [h.is_night for h in horas] == [False] * 12 + [True] * 12


def test_golden_kalams() -> None:
    k = D.kalams(pj_day(), TABLES)
    assert near(k.yamagandam.start, 8, 32) and near(k.yamagandam.end, 10, 3)
    assert near(k.gulika_kalam.start, 11, 33) and near(k.gulika_kalam.end, 13, 4)
    assert near(k.rahu_kalam.start, 13, 4) and near(k.rahu_kalam.end, 14, 34)


def test_golden_clean_parts() -> None:
    day = pj_day()
    horas = D.build_horas(day, "tamil", TABLES)
    blocked = D.blocked_windows(day, TABLES)
    saturn = next(h for h in horas if h.lord == "Saturn")
    assert D.clean_parts(saturn, blocked) == []  # 09:02, inside Yamagandam
    by_start = {hhmm(h.start): h for h in horas}
    assert D.clean_parts(by_start["12:02"], blocked) == []  # Sun: Gulika kalam
    assert D.clean_parts(by_start["13:02"], blocked) == []  # Venus: Gulika then Rahu kalam
    (mars,) = D.clean_parts(by_start["11:02"], blocked)  # clean until Gulika starts
    assert near(mars.end, 11, 33)
    mercury = horas[7]
    parts = D.clean_parts(mercury, blocked)
    assert len(parts) == 1
    assert near(parts[0].start, 14, 34) and parts[0].end == mercury.end
    assert D.clean_parts(horas[0], blocked) == [D.Interval(horas[0].start, horas[0].end)]


def test_golden_blocked_windows_shape() -> None:
    day = pj_day()
    blocked = D.blocked_windows(day, TABLES)
    assert all(a.end <= b.start for a, b in zip(blocked, blocked[1:], strict=False))
    assert all(day.sunrise <= w.start < w.end <= day.next_sunrise for w in blocked)
    reasons = {r for w in blocked for r in w.reasons}
    assert reasons == {"rahu_kalam", "yamagandam", "gulika_kalam", "durmuhurta", "varjyam"}
    # Krittika varjyam falls in the night of this day (about 21:20-22:50 local).
    v = next(w for w in blocked if w.reasons == ("varjyam",))
    assert near(v.start, 21, 20, 2) and near(v.end, 22, 50, 2)


def test_golden_gowri_layer() -> None:
    segs = D.gowri(pj_day(), TABLES)
    assert len(segs) == 16
    assert [s.is_night for s in segs] == [False] * 8 + [True] * 8
    assert all(
        a.end == b.start for a, b in zip(segs, segs[1:], strict=False) if a.is_night == b.is_night
    )
    assert segs[0].name == "Laabam" and segs[0].nature == "good"  # Wednesday, table row unverified


def test_golden_chandrashtama() -> None:
    day = pj_day()
    kanya = D.blocked_windows(day, TABLES, Person(KANYA))
    first = kanya[0]
    assert "chandrashtama" in first.reasons and first.start == day.sunrise
    ends = [w for w in kanya if "chandrashtama" in w.reasons][-1].end
    assert near(ends, 15, 44, 2)  # Moon leaves Mesha, 8th from Kanya
    vrishabha = D.blocked_windows(day, TABLES, Person(VRISHABHA))
    assert all("chandrashtama" not in w.reasons for w in vrishabha)


# ---------------------------------------------------------------------------
# Unit checks on synthetic days
# ---------------------------------------------------------------------------


def test_classical_horas() -> None:
    day = synthetic_day(date(2026, 9, 30))  # Wednesday
    horas = D.build_horas(day, "classical", TABLES)
    assert [h.lord for h in horas[:3]] == ["Mercury", "Moon", "Saturn"]
    assert all(h.end - h.start == timedelta(hours=1) for h in horas)
    day2 = replace(day, sunset=day.sunrise + timedelta(hours=15))
    horas = D.build_horas(day2, "classical", TABLES)
    assert all(h.end - h.start == timedelta(minutes=75) for h in horas[:12])
    assert all(h.end - h.start == timedelta(minutes=45) for h in horas[12:])
    assert [h.is_night for h in horas] == [False] * 12 + [True] * 12
    assert horas[12].lord == TABLES.horas.chaldean_order[(5 + 12) % 7]


def test_kalam_segments_for_every_weekday() -> None:
    rahu = [8, 2, 7, 5, 6, 4, 3]
    yama = [5, 4, 3, 2, 1, 7, 6]
    gulika = [7, 6, 5, 4, 3, 2, 1]
    for offset in range(7):
        day = synthetic_day(date(2026, 9, 27) + timedelta(days=offset))  # 27th is Sunday
        assert day.weekday == offset
        k = D.kalams(day, TABLES)
        seg = timedelta(minutes=90)
        for window, n in (
            (k.rahu_kalam, rahu[offset]),
            (k.yamagandam, yama[offset]),
            (k.gulika_kalam, gulika[offset]),
        ):
            assert window.start == day.sunrise + (n - 1) * seg and window.end - window.start == seg


def test_durmuhurta_day_and_night() -> None:
    sunday = D.durmuhurta(synthetic_day(date(2026, 9, 27)), TABLES)
    assert [(w.start.hour, w.start.minute) for w in sunday] == [(16, 24)]  # 14th of 15 x 48 min
    tuesday = D.durmuhurta(synthetic_day(date(2026, 9, 29)), TABLES)
    night_start = datetime(2026, 9, 29, 18, 0, tzinfo=UTC)
    assert [w.start for w in tuesday] == [
        datetime(2026, 9, 29, 6, 0, tzinfo=UTC) + 3 * timedelta(minutes=48),  # 4th day muhurta
        night_start + 6 * timedelta(minutes=48),  # 7th night muhurta (Drik 23:45)
    ]


def test_varjyam_from_nakshatra_started_previous_day() -> None:
    day = synthetic_day()
    started = day.sunrise - timedelta(hours=18)  # Ashwini began yesterday, lasts 24 h
    day = replace(day, nakshatra_spans=(MoonSpan(0, started, started + timedelta(hours=24)),))
    (w,) = D.varjyam(day, TABLES)
    # Ashwini: ghati 50 of 60 -> 20 h in, lasting 4/60 of 24 h = 96 min.
    assert w.start == started + timedelta(hours=20) and w.end - w.start == timedelta(minutes=96)


def test_varjyam_scales_with_duration_and_clips() -> None:
    day = synthetic_day()
    # Mrigashira: ghati 14 of 60, lasting 4 of 60, over an actual 20 h.
    inside = MoonSpan(4, day.sunrise + timedelta(hours=1), day.sunrise + timedelta(hours=21))
    (w,) = D.varjyam(replace(day, nakshatra_spans=(inside,)), TABLES)
    assert w.end - w.start == timedelta(minutes=80)  # 4/60 of 20 h
    assert w.start == inside.start + timedelta(hours=20 * 14 / 60)

    straddling = MoonSpan(4, day.sunrise - timedelta(hours=5), day.sunrise + timedelta(hours=15))
    (clipped,) = D.varjyam(replace(day, nakshatra_spans=(straddling,)), TABLES)
    assert clipped.start == day.sunrise  # varjyam began 20 min before sunrise
    assert clipped.end == straddling.start + timedelta(hours=20 * 18 / 60)

    outside = MoonSpan(0, day.sunrise - timedelta(hours=30), day.sunrise - timedelta(hours=6))
    assert D.varjyam(replace(day, nakshatra_spans=(outside,)), TABLES) == []


def test_clean_parts_edges() -> None:
    day = synthetic_day()
    hora = Hora(day.sunrise, day.sunrise + timedelta(hours=1), "Sun", False)
    h = timedelta(minutes=1)
    blocked = [
        D.BlockedWindow(day.sunrise - 10 * h, day.sunrise + 10 * h, ("a",)),
        D.BlockedWindow(day.sunrise + 20 * h, day.sunrise + 30 * h, ("b",)),
        D.BlockedWindow(day.sunrise + 30 * h, day.sunrise + 40 * h, ("c",)),
    ]
    assert D.clean_parts(hora, blocked) == [
        D.Interval(day.sunrise + 10 * h, day.sunrise + 20 * h),
        D.Interval(day.sunrise + 40 * h, hora.end),
    ]
    assert D.clean_parts(hora, []) == [D.Interval(hora.start, hora.end)]


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@settings(max_examples=12, deadline=None)
@given(
    d=st.dates(min_value=date(2026, 1, 1), max_value=date(2030, 12, 31)),
    conv=st.sampled_from(["tamil", "classical"]),
)
def test_horas_tile_the_day_and_blocked_windows_are_disjoint(d: date, conv: str) -> None:
    day = pj_day(d)
    horas = D.build_horas(day, conv, TABLES)  # type: ignore[arg-type]
    assert len(horas) == 24
    assert horas[0].start == day.sunrise and horas[-1].end == day.next_sunrise
    assert all(a.end == b.start for a, b in zip(horas, horas[1:], strict=False))
    order = TABLES.horas.chaldean_order
    lords = [order.index(h.lord) for h in horas]
    assert all(b == (a + 1) % 7 for a, b in zip(lords, lords[1:], strict=False))
    assert horas[0].lord == TABLES.horas.weekday_lords[day.weekday]
    blocked = D.blocked_windows(day, TABLES, Person(MESHA))
    assert all(a.end <= b.start for a, b in zip(blocked, blocked[1:], strict=False))
    for h in horas:
        clean = D.clean_parts(h, blocked)
        assert all(h.start <= c.start < c.end <= h.end for c in clean)
