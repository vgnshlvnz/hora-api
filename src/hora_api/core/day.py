"""One panchangam day: horas, inauspicious windows, and the Gowri layer.

Pure calculation. Tables are passed in (see hora_api.core.tables); nothing here reads files.
The day runs sunrise to next sunrise and takes its weekday from the local date of sunrise.
Weekday index: 0 = Sunday ... 6 = Saturday. All datetimes are timezone-aware UTC.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from typing import Final, Literal, Protocol

from hora_api.core import astro
from hora_api.core.astro import Ayanamsa
from hora_api.core.tables import Nature, Tables

Convention = Literal["tamil", "classical"]

REASON_RAHU: Final = "rahu_kalam"
REASON_YAMA: Final = "yamagandam"
REASON_GULIKA: Final = "gulika_kalam"
REASON_DURMUHURTA: Final = "durmuhurta"
REASON_VARJYAM: Final = "varjyam"
REASON_CHANDRASHTAMA: Final = "chandrashtama"

_HORA_SLOT: Final = timedelta(hours=1)
# A nakshatra lasts at most about 27 h; search this far either side of the day to see whole ones.
_NAKSHATRA_MARGIN: Final = timedelta(hours=30)


@dataclass(frozen=True, slots=True)
class Interval:
    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Window:
    """An inauspicious (or otherwise named) interval with a single reason."""

    start: datetime
    end: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class BlockedWindow:
    """A maximal interval over which the same set of reasons applies."""

    start: datetime
    end: datetime
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Hora:
    start: datetime
    end: datetime
    lord: str
    is_night: bool


@dataclass(frozen=True, slots=True)
class GowriSegment:
    start: datetime
    end: datetime
    name: str
    nature: Nature
    is_night: bool


@dataclass(frozen=True, slots=True)
class MoonSpan:
    """The Moon stays in `index` (a nakshatra 0-26 or a rasi 0-11) from start to end."""

    index: int
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class Kalams:
    rahu_kalam: Window
    yamagandam: Window
    gulika_kalam: Window


@dataclass(frozen=True, slots=True)
class Day:
    date_local: date
    weekday: int  # 0 = Sunday
    sunrise: datetime
    sunset: datetime
    next_sunrise: datetime
    # Whole nakshatra spans (they may begin before sunrise or end after next sunrise).
    nakshatra_spans: tuple[MoonSpan, ...]
    # Moon rasi spans clipped to [sunrise, next_sunrise].
    rasi_spans: tuple[MoonSpan, ...]

    @property
    def day_length(self) -> timedelta:
        return self.sunset - self.sunrise

    @property
    def night_length(self) -> timedelta:
        return self.next_sunrise - self.sunset


class HasJanmaRasi(Protocol):
    @property
    def janma_rasi(self) -> int:  # 0-11, Mesha = 0
        ...


def weekday_index(d: date) -> int:
    """0 = Sunday ... 6 = Saturday."""
    return (d.weekday() + 1) % 7


# ---------------------------------------------------------------------------
# Building a day from astronomy
# ---------------------------------------------------------------------------


def make_day(
    date_local: date,
    tz: tzinfo,
    lat: float,
    lon: float,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI,
) -> Day:
    ev = astro.sun_events(date_local, tz, lat, lon)
    found = astro.transitions(
        ev.sunrise - _NAKSHATRA_MARGIN, ev.next_sunrise + _NAKSHATRA_MARGIN, ayanamsa
    )

    nak_changes = [t for t in found if t.kind == "nakshatra"]
    nakshatra_spans = tuple(
        MoonSpan(a.to_index, a.time, b.time)
        for a, b in zip(nak_changes, nak_changes[1:], strict=False)
        if b.time > ev.sunrise and a.time < ev.next_sunrise
    )

    rasi_changes = [t for t in found if t.kind == "rasi" and ev.sunrise < t.time < ev.next_sunrise]
    rasi = astro.moon_state(ev.sunrise, ayanamsa).rasi
    rasi_spans: list[MoonSpan] = []
    cursor = ev.sunrise
    for change in rasi_changes:
        rasi_spans.append(MoonSpan(rasi, cursor, change.time))
        rasi, cursor = change.to_index, change.time
    rasi_spans.append(MoonSpan(rasi, cursor, ev.next_sunrise))

    return Day(
        date_local=date_local,
        weekday=weekday_index(date_local),
        sunrise=ev.sunrise,
        sunset=ev.sunset,
        next_sunrise=ev.next_sunrise,
        nakshatra_spans=nakshatra_spans,
        rasi_spans=tuple(rasi_spans),
    )


# ---------------------------------------------------------------------------
# Horas
# ---------------------------------------------------------------------------


def build_horas(day: Day, convention: Convention, tables: Tables) -> list[Hora]:
    """24 horas from sunrise to next sunrise, lords in Chaldean order from the weekday lord.

    "tamil": 60-minute slots from sunrise; the last slot ends at next sunrise (so may be short
    or long) and `end` records that actual end. A slot is night when its midpoint is after sunset.
    "classical": day length / 12 for the 12 day horas, night length / 12 for the 12 night horas.
    """
    order = tables.horas.chaldean_order
    first = order.index(tables.horas.weekday_lords[day.weekday])

    bounds: list[tuple[datetime, datetime, bool]] = []
    if convention == "tamil":
        for i in range(24):
            start = day.sunrise + i * _HORA_SLOT
            end = day.next_sunrise if i == 23 else start + _HORA_SLOT
            bounds.append((start, end, start + (end - start) / 2 > day.sunset))
    elif convention == "classical":
        day_slot, night_slot = day.day_length / 12, day.night_length / 12
        for i in range(12):
            end = day.sunset if i == 11 else day.sunrise + (i + 1) * day_slot
            bounds.append((day.sunrise + i * day_slot, end, False))
        for i in range(12):
            end = day.next_sunrise if i == 11 else day.sunset + (i + 1) * night_slot
            bounds.append((day.sunset + i * night_slot, end, True))
    else:
        raise ValueError(f"unknown hora convention: {convention!r}")

    return [
        Hora(start, end, order[(first + i) % len(order)], is_night)
        for i, (start, end, is_night) in enumerate(bounds)
    ]


# ---------------------------------------------------------------------------
# Inauspicious windows
# ---------------------------------------------------------------------------


def _part(start: datetime, length: timedelta, parts: int, number: int) -> tuple[datetime, datetime]:
    """Segment `number` (1-based) of `parts` equal segments of `length` starting at `start`."""
    if not 1 <= number <= parts:
        raise ValueError(f"segment {number} outside 1..{parts}")
    seg = length / parts
    return start + (number - 1) * seg, start + number * seg


def kalams(day: Day, tables: Tables) -> Kalams:
    """Rahu kalam, Yamagandam and Gulika kalam: sunrise to sunset in equal parts per weekday."""
    t = tables.kalams

    def window(numbers: Sequence[int], reason: str) -> Window:
        start, end = _part(day.sunrise, day.day_length, t.parts, numbers[day.weekday])
        return Window(start, end, reason)

    return Kalams(
        rahu_kalam=window(t.rahu_kalam, REASON_RAHU),
        yamagandam=window(t.yamagandam, REASON_YAMA),
        gulika_kalam=window(t.gulika_kalam, REASON_GULIKA),
    )


def durmuhurta(day: Day, tables: Tables) -> list[Window]:
    """Day muhurtas (sunrise to sunset / parts) and night muhurtas (sunset to sunrise / parts)."""
    t = tables.durmuhurta
    out = [
        Window(*_part(day.sunrise, day.day_length, t.parts, n), REASON_DURMUHURTA)
        for n in t.day[day.weekday]
    ]
    out += [
        Window(*_part(day.sunset, day.night_length, t.parts, n), REASON_DURMUHURTA)
        for n in t.night[day.weekday]
    ]
    return sorted(out, key=lambda w: w.start)


def varjyam(day: Day, tables: Tables) -> list[Window]:
    """Varjyam per nakshatra, scaled to that nakshatra's actual duration, clipped to the day.

    Uses whole nakshatra spans, so one that began on the previous day still contributes.
    """
    t = tables.varjyam
    out: list[Window] = []
    for span in day.nakshatra_spans:
        duration = span.end - span.start
        for ghati in t.start_ghatis[span.index]:
            start = span.start + duration * (ghati / t.ghatikas_per_nakshatra)
            end = start + duration * (t.duration_ghatikas / t.ghatikas_per_nakshatra)
            start, end = max(start, day.sunrise), min(end, day.next_sunrise)
            if start < end:
                out.append(Window(start, end, REASON_VARJYAM))
    return sorted(out, key=lambda w: w.start)


def gowri(day: Day, tables: Tables) -> list[GowriSegment]:
    """Gowri panchangam (Nalla Neram) segments for the day then the night. A separate layer."""
    t = tables.gowri
    out: list[GowriSegment] = []
    for names, start, length, is_night in (
        (t.day[day.weekday], day.sunrise, day.day_length, False),
        (t.night[day.weekday], day.sunset, day.night_length, True),
    ):
        seg = length / t.segments
        for i, name in enumerate(names):
            out.append(
                GowriSegment(start + i * seg, start + (i + 1) * seg, name, t.nature[name], is_night)
            )
    return out


def chandrashtama(day: Day, person: HasJanmaRasi) -> list[Window]:
    """Spans of the day when the Moon is in the 8th rasi from the person's janma rasi."""
    return [
        Window(s.start, s.end, REASON_CHANDRASHTAMA)
        for s in day.rasi_spans
        if (s.index - person.janma_rasi) % 12 + 1 == 8
    ]


def blocked_windows(
    day: Day, tables: Tables, person: HasJanmaRasi | None = None
) -> list[BlockedWindow]:
    """All hard-filter windows as sorted, non-overlapping intervals with their reasons.

    The day is cut at every window boundary; each piece carries exactly the reasons active over
    it, and neighbouring pieces with identical reasons are joined.
    """
    k = kalams(day, tables)
    windows: list[Window] = [k.rahu_kalam, k.yamagandam, k.gulika_kalam]
    windows += durmuhurta(day, tables)
    windows += varjyam(day, tables)
    if person is not None:
        windows += chandrashtama(day, person)

    clipped = [
        Window(max(w.start, day.sunrise), min(w.end, day.next_sunrise), w.reason)
        for w in windows
        if max(w.start, day.sunrise) < min(w.end, day.next_sunrise)
    ]
    cuts = sorted({c for w in clipped for c in (w.start, w.end)})

    pieces: list[BlockedWindow] = []
    for a, b in zip(cuts, cuts[1:], strict=False):
        reasons = tuple(sorted({w.reason for w in clipped if w.start <= a and b <= w.end}))
        if not reasons:
            continue
        if pieces and pieces[-1].end == a and pieces[-1].reasons == reasons:
            pieces[-1] = BlockedWindow(pieces[-1].start, b, reasons)
        else:
            pieces.append(BlockedWindow(a, b, reasons))
    return pieces


def clean_parts(hora: Hora, blocked: Sequence[BlockedWindow]) -> list[Interval]:
    """The sub-intervals of `hora` not covered by any blocked window."""
    parts: list[Interval] = []
    cursor = hora.start
    for w in sorted(blocked, key=lambda b: b.start):
        if w.end <= cursor or w.start >= hora.end:
            continue
        if w.start > cursor:
            parts.append(Interval(cursor, w.start))
        cursor = max(cursor, w.end)
    if cursor < hora.end:
        parts.append(Interval(cursor, hora.end))
    return parts
