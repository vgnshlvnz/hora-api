"""Astronomical primitives on top of Swiss Ephemeris (pyswisseph).

Pure calculation: no I/O beyond the ephemeris itself, no FastAPI. Datetimes crossing this API
are timezone-aware; results are always UTC.

Julian day numbers are derived from UTC directly (UT1 - UTC is under 0.9 s, far below the
tolerances used here). Positions use the built-in Moshier ephemeris so results do not depend on
ephemeris data files being installed.

Index conventions (0-based unless noted): nakshatra 0-26 (Ashwini = 0), pada 1-4, rasi 0-11
(Mesha = 0), tithi 1-30. Names are classical lookup tables and live outside core.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from enum import StrEnum
from typing import Final, Literal

import swisseph as swe

NAKSHATRA_SPAN: Final = 360.0 / 27.0
PADA_SPAN: Final = NAKSHATRA_SPAN / 4.0
RASI_SPAN: Final = 30.0
TITHI_SPAN: Final = 12.0

# Moshier: no data files needed, sub-arcsecond for Sun and Moon over the supported range.
EPHEMERIS_FLAGS: Final = swe.FLG_MOSEPH
# Disc centre, Swiss Ephemeris default refraction (atpress/attemp of 0 mean "use defaults").
DEFAULT_RISE_FLAGS: Final = swe.BIT_DISC_CENTER

_UNIX_EPOCH_JD: Final = 2440587.5
_SECONDS_PER_DAY: Final = 86400.0
_SAMPLE_STEP_DAYS: Final = 30.0 / (24 * 60)  # shorter than any nakshatra/rasi/tithi
_DEFAULT_TOLERANCE_SECONDS: Final = 1.0
_DEFAULT_SID_MODE: Final = swe.SIDM_FAGAN_BRADLEY  # Swiss Ephemeris start-up default

_sidereal_lock = threading.RLock()


class Ayanamsa(StrEnum):
    """Supported ayanamsas; the value is the public spelling."""

    LAHIRI = "lahiri"
    KP = "kp"  # Krishnamurti


_SIDM: Final = {
    Ayanamsa.LAHIRI: swe.SIDM_LAHIRI,
    Ayanamsa.KP: swe.SIDM_KRISHNAMURTI,
}


@dataclass(frozen=True, slots=True)
class SunEvents:
    sunrise: datetime
    sunset: datetime
    next_sunrise: datetime


@dataclass(frozen=True, slots=True)
class MoonState:
    longitude: float  # sidereal, degrees in [0, 360)
    nakshatra: int  # 0-26
    pada: int  # 1-4
    rasi: int  # 0-11


TransitionKind = Literal["nakshatra", "rasi", "tithi"]
_KIND_ORDER: Final[dict[TransitionKind, int]] = {"nakshatra": 0, "rasi": 1, "tithi": 2}


@dataclass(frozen=True, slots=True)
class Transition:
    """A change in nakshatra, rasi or tithi at an exact UTC time."""

    kind: TransitionKind
    time: datetime
    from_index: int
    to_index: int


# ---------------------------------------------------------------------------
# Time conversion
# ---------------------------------------------------------------------------


def _to_jd(t: datetime) -> float:
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return t.timestamp() / _SECONDS_PER_DAY + _UNIX_EPOCH_JD


def _from_jd(jd: float) -> datetime:
    seconds = (jd - _UNIX_EPOCH_JD) * _SECONDS_PER_DAY
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Sidereal mode (process-global in Swiss Ephemeris; wrapped so it never leaks)
# ---------------------------------------------------------------------------


@contextmanager
def _sidereal(ayanamsa: Ayanamsa) -> Iterator[None]:
    with _sidereal_lock:
        swe.set_sid_mode(_SIDM[ayanamsa])
        try:
            yield
        finally:
            swe.set_sid_mode(_DEFAULT_SID_MODE)


def _moon_sidereal_longitude_jd(jd: float, ayanamsa: Ayanamsa) -> float:
    with _sidereal(ayanamsa):
        pos, _ = swe.calc_ut(jd, swe.MOON, EPHEMERIS_FLAGS | swe.FLG_SIDEREAL)
    return float(pos[0]) % 360.0


def _tithi_index_jd(jd: float) -> int:
    """Tithi 1-30 from the Moon-Sun elongation (identical in tropical and sidereal)."""
    moon, _ = swe.calc_ut(jd, swe.MOON, EPHEMERIS_FLAGS)
    sun, _ = swe.calc_ut(jd, swe.SUN, EPHEMERIS_FLAGS)
    elongation = (moon[0] - sun[0]) % 360.0
    return min(int(elongation // TITHI_SPAN), 29) + 1


def _state_from_longitude(lon: float) -> MoonState:
    lon %= 360.0
    nakshatra = min(int(lon // NAKSHATRA_SPAN), 26)
    pada = min(int((lon - nakshatra * NAKSHATRA_SPAN) // PADA_SPAN), 3) + 1
    return MoonState(lon, nakshatra, pada, min(int(lon // RASI_SPAN), 11))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def moon_state(t: datetime, ayanamsa: Ayanamsa = Ayanamsa.LAHIRI) -> MoonState:
    """Sidereal longitude, nakshatra, pada and rasi of the Moon at `t`."""
    return _state_from_longitude(_moon_sidereal_longitude_jd(_to_jd(t), ayanamsa))


def ascendant(t: datetime, lat: float, lon: float, ayanamsa: Ayanamsa = Ayanamsa.LAHIRI) -> float:
    """Sidereal longitude of the ascendant (lagna) at `t` for a place, in degrees [0, 360).

    The rasi of the lagna is `int(ascendant // 30)`.
    """
    with _sidereal(ayanamsa):
        _, ascmc = swe.houses_ex(_to_jd(t), lat, lon, b"W", swe.FLG_SIDEREAL)
    return float(ascmc[0]) % 360.0


def paksha(t: datetime) -> Literal["shukla", "krishna"]:
    """Waxing (shukla, tithi 1-15) or waning (krishna, tithi 16-30) fortnight at `t`."""
    return "shukla" if tithi(t) <= 15 else "krishna"


def tithi(t: datetime) -> int:
    """Tithi number 1-30 at `t` (1-15 shukla, 16-30 krishna)."""
    return _tithi_index_jd(_to_jd(t))


def sun_events(
    date_local: date,
    tz: tzinfo,
    lat: float,
    lon: float,
    *,
    rise_flags: int = DEFAULT_RISE_FLAGS,
    altitude_m: float = 0.0,
) -> SunEvents:
    """Sunrise, sunset and next sunrise for the local calendar day `date_local`.

    `rise_flags` are extra Swiss Ephemeris `rsmi` bits (default: disc centre); the rise/set
    direction bits are added here. Refraction uses Swiss Ephemeris defaults.
    """
    geopos = (lon, lat, altitude_m)
    day_start = datetime.combine(date_local, time.min, tzinfo=tz)

    def event(after_jd: float, kind: int) -> float:
        code, tret = swe.rise_trans(
            after_jd, swe.SUN, kind | rise_flags, geopos, 0.0, 0.0, EPHEMERIS_FLAGS
        )
        if code != 0:
            raise ValueError(f"sun does not rise/set at lat={lat}, lon={lon} near {date_local}")
        return float(tret[0])

    sunrise = event(_to_jd(day_start), swe.CALC_RISE)
    sunset = event(sunrise, swe.CALC_SET)
    # Skip past the current rise so the next search cannot return it again.
    next_sunrise = event(sunrise + 1.0 / 24.0, swe.CALC_RISE)
    return SunEvents(_from_jd(sunrise), _from_jd(sunset), _from_jd(next_sunrise))


def transitions(
    start: datetime,
    end: datetime,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI,
    *,
    tolerance_seconds: float = _DEFAULT_TOLERANCE_SECONDS,
) -> list[Transition]:
    """Changes in nakshatra, rasi and tithi inside [start, end], ordered by time.

    Each time is found by bisection to within `tolerance_seconds` (default 1 s). Events that
    share a boundary (nakshatra and rasi both change at 0, 120 and 240 degrees) get the same
    time to within that tolerance and are ordered nakshatra, rasi, tithi.
    """
    start_jd, end_jd = _to_jd(start), _to_jd(end)
    if end_jd < start_jd:
        raise ValueError("end must not be before start")
    tol = tolerance_seconds / _SECONDS_PER_DAY

    def indices(jd: float) -> tuple[int, int, int]:
        s = _state_from_longitude(_moon_sidereal_longitude_jd(jd, ayanamsa))
        return s.nakshatra, s.rasi, _tithi_index_jd(jd)

    found: list[tuple[float, TransitionKind, int, int]] = []
    kinds: tuple[TransitionKind, ...] = ("nakshatra", "rasi", "tithi")

    a = start_jd
    ia = indices(a)
    while a < end_jd:
        b = min(a + _SAMPLE_STEP_DAYS, end_jd)
        ib = indices(b)
        for k, kind in enumerate(kinds):
            if ia[k] == ib[k]:
                continue
            lo, hi = a, b
            while hi - lo > tol:
                mid = (lo + hi) / 2.0
                if indices(mid)[k] == ia[k]:
                    lo = mid
                else:
                    hi = mid
            found.append((hi, kind, ia[k], ib[k]))
        a, ia = b, ib

    found.sort(key=lambda f: (f[0], _KIND_ORDER[f[1]]))
    return [Transition(kind, _from_jd(jd), frm, to) for jd, kind, frm, to in found]


__all__ = [
    "DEFAULT_RISE_FLAGS",
    "NAKSHATRA_SPAN",
    "Ayanamsa",
    "MoonState",
    "SunEvents",
    "Transition",
    "ascendant",
    "moon_state",
    "paksha",
    "sun_events",
    "tithi",
    "transitions",
]
