"""Chat cards: client-neutral, ready-to-show JSON built from a computed day.

A card is a title, a subtitle and ordered sections of label/value rows, each row carrying a
tone (good / bad / neutral). All times are strings in the request's timezone, "HH:MM", with
"+1" appended for times after local midnight. Clients render the structure their own way;
sections have stable ids so a small client (an ESP32) can pick just the ones it wants.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from hora_api.api.models import TopWindow, TopWindows
from hora_api.api.service import ComputedDay, RequestParams
from hora_api.core import astro
from hora_api.core import day as D
from hora_api.core.tables import Tables
from hora_api.scoring.personal import Profile, ScoredHora, chandrabala, tarabala
from hora_api.scoring.rasi import RasiMatrix
from hora_api.scoring.tables import NameTable, Quality, ScoringTables

Tone = Literal["good", "bad", "neutral"]

_REASON_LABELS = {
    D.REASON_RAHU: "Rahu kalam",
    D.REASON_YAMA: "Yamagandam",
    D.REASON_GULIKA: "Gulika kalam",
    D.REASON_DURMUHURTA: "Durmuhurta",
    D.REASON_VARJYAM: "Varjyam",
    D.REASON_CHANDRASHTAMA: "Chandrashtama",
}


class CardRow(BaseModel):
    label: str
    value: str
    tone: Tone = "neutral"


class CardSection(BaseModel):
    # Stable ids. Day: sun, moon, avoid, nalla_neram, horas. Rasi: chandrashtama, best, all.
    # Personal: top, blocked, tara_chandra.
    id: str
    title: str
    rows: list[CardRow]


class Card(BaseModel):
    kind: Literal["day", "rasi", "personal"]
    title: str
    subtitle: str
    sections: list[CardSection]
    footer: str | None = None
    unverified_tables: list[str] = []


class _Clock:
    """Formats UTC datetimes as local "HH:MM" (rounded to the minute), "+1" past midnight."""

    def __init__(self, tz: ZoneInfo, day: date) -> None:
        self.tz, self.day = tz, day

    def at(self, t: datetime) -> str:
        local = t.astimezone(self.tz) + timedelta(seconds=30)
        suffix = "+1" if local.date() > self.day else ""
        return f"{local:%H:%M}{suffix}"

    def span(self, start: datetime, end: datetime) -> str:
        return f"{self.at(start)}–{self.at(end)}"


def _title(prefix: str, d: date) -> str:
    return f"{prefix}{d:%A} {d.day} {d:%b %Y}"


def _subtitle(p: RequestParams) -> str:
    return f"{p.tz_name} · {p.lat:.3f}, {p.lon:.3f} · {p.convention} · {p.ayanamsa.value}"


def _footer(unverified: list[str]) -> str | None:
    if not unverified:
        return None
    return f"Unverified tables in use: {', '.join(unverified)}."


def _chain(first: str, changes: list[tuple[str, datetime]], clock: _Clock) -> str:
    if not changes:
        return f"{first} all day"
    return first + "".join(f" → {name} ({clock.at(t)})" for name, t in changes)


def day_card(
    p: RequestParams,
    cd: ComputedDay,
    tables: Tables,
    names: NameTable,
    unverified: list[str],
) -> Card:
    """Sun, Moon, windows to avoid, Nalla Neram (Gowri, its own layer) and the horas."""
    clock = _Clock(p.tz, p.date)
    day = cd.day

    sun = CardSection(
        id="sun",
        title="Sun",
        rows=[
            CardRow(label="Sunrise", value=clock.at(day.sunrise)),
            CardRow(label="Sunset", value=clock.at(day.sunset)),
            CardRow(label="Next sunrise", value=clock.at(day.next_sunrise)),
        ],
    )

    moon_now = astro.moon_state(day.sunrise, p.ayanamsa)
    tithi_now = astro.tithi(day.sunrise)
    by_kind: dict[str, list[astro.Transition]] = {"nakshatra": [], "rasi": [], "tithi": []}
    for t in cd.transitions:
        by_kind[t.kind].append(t)
    moon = CardSection(
        id="moon",
        title="Moon",
        rows=[
            CardRow(
                label="Nakshatra",
                value=_chain(
                    names.nakshatras[moon_now.nakshatra],
                    [(names.nakshatras[t.to_index], t.time) for t in by_kind["nakshatra"]],
                    clock,
                ),
            ),
            CardRow(
                label="Rasi",
                value=_chain(
                    names.rasis[moon_now.rasi],
                    [(names.rasis[t.to_index], t.time) for t in by_kind["rasi"]],
                    clock,
                ),
            ),
            CardRow(
                label="Tithi",
                value=_chain(
                    str(tithi_now), [(str(t.to_index), t.time) for t in by_kind["tithi"]], clock
                ),
            ),
        ],
    )

    k = D.kalams(day, tables)
    windows = [k.rahu_kalam, k.yamagandam, k.gulika_kalam]
    windows += D.durmuhurta(day, tables) + D.varjyam(day, tables)
    avoid = CardSection(
        id="avoid",
        title="Avoid",
        rows=[
            CardRow(label=_REASON_LABELS[w.reason], value=clock.span(w.start, w.end), tone="bad")
            for w in sorted(windows, key=lambda w: w.start)
        ],
    )

    nalla = CardSection(
        id="nalla_neram",
        title="Nalla Neram (Gowri)",
        rows=[
            CardRow(label=g.name, value=clock.span(g.start, g.end), tone="good")
            for g in cd.gowri
            if g.nature == "good"
        ],
    )

    horas = CardSection(
        id="horas",
        title=f"Horas ({p.convention})",
        rows=[CardRow(label=clock.span(h.start, h.end), value=h.lord) for h in cd.horas],
    )

    return Card(
        kind="day",
        title=_title("", p.date),
        subtitle=_subtitle(p),
        sections=[s for s in (sun, moon, avoid, nalla, horas) if s.rows],
        footer=_footer(unverified),
        unverified_tables=unverified,
    )


def _span_words(start: datetime, end: datetime, day: D.Day, clock: _Clock) -> str:
    if start <= day.sunrise and end >= day.next_sunrise:
        return "all day"
    if start <= day.sunrise:
        return f"until {clock.at(end)}"
    if end >= day.next_sunrise:
        return f"from {clock.at(start)}"
    return clock.span(start, end)


def rasi_card(
    p: RequestParams,
    cd: ComputedDay,
    matrix: RasiMatrix,
    names: NameTable,
    unverified: list[str],
) -> Card:
    """Chandrashtama rasis, the three best rasis by day percentage, and all twelve."""
    clock = _Clock(p.tz, p.date)
    day = cd.day

    chandrashtama = CardSection(
        id="chandrashtama",
        title="Chandrashtama (Moon 8th from the rasi)",
        rows=[
            CardRow(
                label=names.rasis[(span.index - 7) % 12],
                value=_span_words(span.start, span.end, day, clock),
                tone="bad",
            )
            for span in day.rasi_spans
        ],
    )

    def value(row_day: float | None, clean: float) -> str:
        pct = "blocked all day" if row_day is None else f"{row_day:g}%"
        return f"{pct} · {clean:g}% of the day clean"

    scored = [r for r in matrix.rasis if r.day_percent is not None]
    ranked = sorted(scored, key=lambda r: (-(r.day_percent or 0.0), -r.clean_percent, r.rasi))
    best = CardSection(
        id="best",
        title="Best rasis (by day percentage, then clean share)",
        rows=[
            CardRow(label=r.name, value=value(r.day_percent, r.clean_percent), tone="good")
            for r in ranked[:3]
        ],
    )
    everything = CardSection(
        id="all",
        title="All rasis",
        rows=[
            CardRow(
                label=r.name,
                value=value(r.day_percent, r.clean_percent),
                tone="bad" if r.day_percent is None else "neutral",
            )
            for r in matrix.rasis
        ],
    )

    return Card(
        kind="rasi",
        title=_title("Rasis · ", p.date),
        subtitle=_subtitle(p),
        sections=[s for s in (chandrashtama, best, everything) if s.rows],
        footer=_footer(unverified),
        unverified_tables=unverified,
    )


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


_QUALITY_TONE: dict[Quality, Tone] = {
    "good": "good",
    "bad": "bad",
    "neutral": "neutral",
    "conditional": "neutral",
}


def _score(score: float) -> str:
    return f"{score:g}"


def personal_card(
    p: RequestParams,
    cd: ComputedDay,
    profile: Profile,
    scored: list[ScoredHora],
    top: TopWindows,
    tables: ScoringTables,
    unverified: list[str],
) -> Card:
    """Best windows, why horas are blocked, and the day's tarabala and chandrabala."""
    clock = _Clock(p.tz, p.date)
    day = cd.day

    def top_row(label: str, w: TopWindow | None) -> CardRow:
        if w is None:
            return CardRow(label=label, value="none")
        return CardRow(
            label=label,
            value=f"{clock.span(w.start, w.end)} {w.lord} ({_score(w.score)})",
            tone="good",
        )

    best = CardSection(
        id="top",
        title="Best windows",
        rows=[
            top_row("Best overall", top.best_overall),
            top_row("Best before noon", top.best_before_noon),
            top_row("Best after sunset", top.best_after_sunset),
        ],
    )

    blocked = CardSection(
        id="blocked",
        title="Fully blocked horas",
        rows=[
            CardRow(
                label=clock.span(h.start, h.end),
                value=f"{h.lord} — {', '.join(_REASON_LABELS[r] for r in h.blocked_reasons)}",
                tone="bad",
            )
            for h in scored
            if h.score is None
        ],
    )

    tara_rows = []
    for span in day.nakshatra_spans:
        t = tarabala(profile.janma_nakshatra, span.index, tables)
        tara_rows.append(
            CardRow(
                label=f"Tarabala {_span_words(span.start, span.end, day, clock)}",
                value=f"{t.name} ({_ordinal(t.number)}, {t.quality})",
                tone=_QUALITY_TONE[t.quality],
            )
        )
    chandra_rows = []
    for span in day.rasi_spans:
        c = chandrabala(profile.janma_rasi, span.index, tables)
        note = "Chandrashtama" if c.house == 8 else c.quality
        chandra_rows.append(
            CardRow(
                label=f"Chandrabala {_span_words(span.start, span.end, day, clock)}",
                value=f"{_ordinal(c.house)} house ({note})",
                tone=_QUALITY_TONE[c.quality],
            )
        )
    moon = CardSection(id="tara_chandra", title="Tara and chandra", rows=tara_rows + chandra_rows)

    return Card(
        kind="personal",
        title=_title(f"{profile.display_name} · ", p.date),
        subtitle=_subtitle(p),
        sections=[s for s in (best, blocked, moon) if s.rows],
        footer=_footer(unverified),
        unverified_tables=unverified,
    )
