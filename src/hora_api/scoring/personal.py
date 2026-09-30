"""Personal hora scoring: tarabala + chandrabala + hora-lord rank (+ dasha), per hora.

The same code path serves any profile. Hard filters (Rahu kalam, Yamagandam, Gulika kalam,
Durmuhurta, Varjyam, Chandrashtama) come from hora_api.core.day; a window that is blocked is
removed, never scored down. Weights and quality values come from ScoringSettings.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, BeforeValidator, Field, field_validator

from hora_api.core import astro
from hora_api.core.astro import Ayanamsa
from hora_api.core.day import (
    BlockedWindow,
    Day,
    Hora,
    Interval,
    MoonSpan,
    blocked_windows,
    clean_parts,
)
from hora_api.core.tables import Tables
from hora_api.data.loader import load_scoring_tables
from hora_api.scoring.settings import ScoringSettings
from hora_api.scoring.tables import FunctionalEntry, Quality, ScoringTables

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _default_tables() -> ScoringTables:
    return load_scoring_tables()


def _resolver(kind: Literal["nakshatras", "rasis"]) -> Any:
    """Accept an index or a classical name ("Rohini", "vrishabha") and return the index."""

    def resolve(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        names = getattr(_default_tables().names, kind)
        key = value.strip().lower().replace("_", " ")
        for i, name in enumerate(names):
            if name.lower() == key:
                return i
        raise ValueError(f"unknown {kind[:-1]} name: {value!r}")

    return resolve


Nakshatra = Annotated[int, Field(ge=0, le=26), BeforeValidator(_resolver("nakshatras"))]
Rasi = Annotated[int, Field(ge=0, le=11), BeforeValidator(_resolver("rasis"))]


class DashaPeriod(BaseModel):
    """A dasha (maha) or bhukti (antar) period. Times are timezone-aware."""

    lord: str
    start: AwareDatetime
    end: AwareDatetime
    level: Literal["maha", "antar"] = "maha"


class Profile(BaseModel):
    """Natal data needed for scoring. Indices: nakshatra 0-26, rasi/lagna 0-11."""

    id: str
    display_name: str
    janma_nakshatra: Nakshatra
    janma_rasi: Rasi
    lagna: Rasi
    dasha: list[DashaPeriod] | None = None
    tz_home: str

    @field_validator("tz_home")
    @classmethod
    def _valid_zone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown IANA timezone: {v!r}") from e
        return v


def derive_profile(
    birth_dt: datetime,
    lat: float,
    lon: float,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI,
    *,
    id: str,  # noqa: A002
    display_name: str,
    tz_home: str,
    dasha: list[DashaPeriod] | None = None,
) -> Profile:
    """Derive janma nakshatra, janma rasi and lagna from birth data via core.astro."""
    moon = astro.moon_state(birth_dt, ayanamsa)
    lagna = int(astro.ascendant(birth_dt, lat, lon, ayanamsa) // 30)
    return Profile(
        id=id,
        display_name=display_name,
        janma_nakshatra=moon.nakshatra,
        janma_rasi=moon.rasi,
        lagna=lagna,
        dasha=dasha,
        tz_home=tz_home,
    )


class TaraDetail(BaseModel):
    number: int
    name: str
    quality: Quality


class ChandraDetail(BaseModel):
    house: int
    quality: Quality


class TaraChange(BaseModel):
    at: AwareDatetime
    before: TaraDetail
    after: TaraDetail


class ChandraChange(BaseModel):
    at: AwareDatetime
    before: ChandraDetail
    after: ChandraDetail


class TimeSpan(BaseModel):
    start: AwareDatetime
    end: AwareDatetime


class ScoreComponents(BaseModel):
    """Points contributed by each component; they add up to the score (0-100)."""

    tara: float
    chandra: float
    hora: float
    dasha: float | None = None


class ScoredHora(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    lord: str
    is_night: bool
    score: float | None  # None when the hora is fully blocked
    clean_parts: list[TimeSpan]
    blocked_reasons: list[str]
    # Components and details are reported even for fully blocked horas, judged over the whole
    # hora, so clients can show them; the score itself is None.
    components: ScoreComponents
    tara: TaraDetail
    chandra: ChandraDetail
    hora_rank: int
    # Set when tara/chandra changes inside the hora: both values and the change time.
    # `tara`/`chandra` above hold the value covering the majority of the hora's clean time.
    tara_change: TaraChange | None = None
    chandra_change: ChandraChange | None = None


# ---------------------------------------------------------------------------
# Component functions
# ---------------------------------------------------------------------------


def tarabala(janma_nak: int, day_nak: int, tables: ScoringTables | None = None) -> TaraDetail:
    """Tara of the day's nakshatra counted from the janma nakshatra."""
    t = (tables or _default_tables()).tara
    count = ((day_nak - janma_nak) % 27) + 1
    number = ((count - 1) % 9) + 1
    return TaraDetail(number=number, name=t.names[number - 1], quality=t.quality[number - 1])


def chandrabala(
    janma_rasi: int, moon_rasi: int, tables: ScoringTables | None = None
) -> ChandraDetail:
    """House of the Moon counted from the janma rasi (house 8 is Chandrashtama)."""
    t = (tables or _default_tables()).chandra
    house = ((moon_rasi - janma_rasi) % 12) + 1
    return ChandraDetail(house=house, quality=t.quality[house - 1])


def _quality_value(quality: Quality, settings: ScoringSettings) -> float:
    return {
        "good": settings.value_good,
        "bad": settings.value_bad,
        "neutral": settings.value_neutral,
        "conditional": settings.chandra_conditional_value,
    }[quality]


def tara_value(tara: TaraDetail, settings: ScoringSettings) -> float:
    if tara.number == 1:
        return settings.tara_janma_value
    return _quality_value(tara.quality, settings)


def chandra_value(chandra: ChandraDetail, settings: ScoringSettings) -> float:
    return _quality_value(chandra.quality, settings)


def _functional_rank(entry: FunctionalEntry, lord: str) -> int:
    if lord == entry.yogakaraka or lord == entry.lagna_lord:
        return 3
    if lord in entry.trikona_lords:
        return 2
    if lord in entry.neutral_lords:
        return 1
    return 0


def hora_lord_rank(lagna: int, lord: str, tables: ScoringTables | None = None) -> int:
    """Rank 0-3 of a planet as hora lord for a lagna, from its functional nature."""
    return _functional_rank((tables or _default_tables()).functional[lagna], lord)


def hora_lord_ranks(lagna: int, tables: ScoringTables | None = None) -> dict[str, int]:
    t = tables or _default_tables()
    return {p: _functional_rank(t.functional[lagna], p) for p in t.names.planets}


def dasha_match(
    profile: Profile,
    lord: str,
    at: datetime,
    settings: ScoringSettings,
    tables: ScoringTables | None = None,
) -> float | None:
    """0-1 match of the hora lord with the running dasha/bhukti lords; None without dasha data."""
    if not profile.dasha:
        return None
    friends = (tables or _default_tables()).friends
    running = [p.lord for p in profile.dasha if p.start <= at < p.end]
    best = 0.0
    for dasha_lord in running:
        if lord == dasha_lord:
            best = max(best, settings.dasha_match_value)
        elif lord in friends.get(dasha_lord, frozenset()):
            best = max(best, settings.dasha_friend_value)
    return best


# ---------------------------------------------------------------------------
# Scoring a day
# ---------------------------------------------------------------------------


def _overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> float:
    return max(0.0, (min(a_end, b_end) - max(a_start, b_start)).total_seconds())


def _pieces(hora: Hora, spans: Sequence[MoonSpan]) -> list[tuple[int, datetime, datetime]]:
    """(index, start, end) of each Moon span inside the hora, in time order."""
    return [
        (s.index, max(s.start, hora.start), min(s.end, hora.end))
        for s in spans
        if s.start < hora.end and s.end > hora.start
    ]


def _majority(
    pieces: list[tuple[int, datetime, datetime]], clean: Sequence[Interval], hora: Hora
) -> int:
    """Position of the piece covering most of the hora's clean time (whole hora if none)."""
    windows = [(c.start, c.end) for c in clean] or [(hora.start, hora.end)]
    coverage = [sum(_overlap(s, e, w0, w1) for w0, w1 in windows) for _, s, e in pieces]
    return coverage.index(max(coverage))  # ties go to the earlier piece


def score_horas(
    horas: Sequence[Hora],
    day: Day,
    profile: Profile,
    tables: Tables,
    settings: ScoringSettings | None = None,
    scoring_tables: ScoringTables | None = None,
) -> list[ScoredHora]:
    """Score each hora for a profile; fully blocked horas get score None."""
    cfg = settings or ScoringSettings()
    st = scoring_tables or _default_tables()
    blocked = blocked_windows(day, tables, profile)

    w_dasha = cfg.weight_dasha_when_given if profile.dasha else 0.0
    total_weight = cfg.weight_tara + cfg.weight_chandra + cfg.weight_hora + w_dasha
    scale = 100.0 / total_weight

    out: list[ScoredHora] = []
    for hora in horas:
        clean = clean_parts(hora, blocked)
        reasons = sorted(
            {r for w in blocked if w.start < hora.end and w.end > hora.start for r in w.reasons}
        )

        tara_pieces = _pieces(hora, day.nakshatra_spans)
        taras = [tarabala(profile.janma_nakshatra, i, st) for i, _, _ in tara_pieces]
        used_t = _majority(tara_pieces, clean, hora)
        tara_change = (
            TaraChange(at=tara_pieces[1][1], before=taras[0], after=taras[-1])
            if len(taras) > 1
            else None
        )

        chandra_pieces = _pieces(hora, day.rasi_spans)
        chandras = [chandrabala(profile.janma_rasi, i, st) for i, _, _ in chandra_pieces]
        used_c = _majority(chandra_pieces, clean, hora)
        chandra_change = (
            ChandraChange(at=chandra_pieces[1][1], before=chandras[0], after=chandras[-1])
            if len(chandras) > 1
            else None
        )

        rank = hora_lord_rank(profile.lagna, hora.lord, st)
        mid = hora.start + (hora.end - hora.start) / 2
        dasha = dasha_match(profile, hora.lord, mid, cfg, st)

        points_tara = cfg.weight_tara * tara_value(taras[used_t], cfg) * scale
        points_chandra = cfg.weight_chandra * chandra_value(chandras[used_c], cfg) * scale
        points_hora = cfg.weight_hora * (rank / 3.0) * scale
        points_dasha = None if dasha is None else w_dasha * dasha * scale
        total = points_tara + points_chandra + points_hora + (points_dasha or 0.0)

        out.append(
            ScoredHora(
                start=hora.start,
                end=hora.end,
                lord=hora.lord,
                is_night=hora.is_night,
                score=round(total, 1) if clean else None,
                clean_parts=[TimeSpan(start=c.start, end=c.end) for c in clean],
                blocked_reasons=reasons,
                components=ScoreComponents(
                    tara=round(points_tara, 1),
                    chandra=round(points_chandra, 1),
                    hora=round(points_hora, 1),
                    dasha=None if points_dasha is None else round(points_dasha, 1),
                ),
                tara=taras[used_t],
                chandra=chandras[used_c],
                hora_rank=rank,
                tara_change=tara_change,
                chandra_change=chandra_change,
            )
        )
    return out


__all__ = [
    "BlockedWindow",
    "ChandraDetail",
    "DashaPeriod",
    "Profile",
    "ScoredHora",
    "TaraDetail",
    "chandrabala",
    "dasha_match",
    "derive_profile",
    "hora_lord_rank",
    "hora_lord_ranks",
    "score_horas",
    "tarabala",
]
