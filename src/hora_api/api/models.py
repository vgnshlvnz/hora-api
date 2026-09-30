"""Response models. All datetimes are localised to the request's IANA timezone."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from pydantic import AwareDatetime, BaseModel

from hora_api.core.astro import Ayanamsa
from hora_api.core.day import Convention
from hora_api.scoring.personal import ScoredHora
from hora_api.scoring.rasi import HoraInfo, RasiRow


class Meta(BaseModel):
    date: date
    weekday: str
    tz: str
    lat: float
    lon: float
    convention: Convention
    ayanamsa: Ayanamsa


class SunOut(BaseModel):
    sunrise: AwareDatetime
    sunset: AwareDatetime
    next_sunrise: AwareDatetime


class TransitionOut(BaseModel):
    kind: str  # nakshatra | rasi | tithi
    time: AwareDatetime
    from_index: int  # nakshatra 0-26, rasi 0-11, tithi 1-30
    to_index: int
    from_name: str | None = None  # nakshatra and rasi only
    to_name: str | None = None


class HoraOut(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    lord: str
    is_night: bool


class BlockedOut(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    reasons: list[str]


class GowriOut(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    name: str
    nature: str
    is_night: bool


class DayResponse(BaseModel):
    meta: Meta
    sun: SunOut
    transitions: list[TransitionOut]
    horas: list[HoraOut]
    blocked: list[BlockedOut]
    gowri: list[GowriOut]  # separate layer, never blended into scores
    unverified_tables: list[str]  # tables in use that are marked verify: true


class ProfileSummary(BaseModel):
    id: str
    display_name: str


class TopWindow(BaseModel):
    """A clean stretch of a hora recommended by score."""

    start: AwareDatetime
    end: AwareDatetime
    lord: str
    score: float


class TopWindows(BaseModel):
    best_overall: TopWindow | None
    best_before_noon: TopWindow | None
    best_after_sunset: TopWindow | None


class DashaOut(BaseModel):
    """A dasha ("maha") or bhukti ("antar") in force at some point of the day."""

    level: str
    lord: str
    start: AwareDatetime
    end: AwareDatetime


class PersonalResponse(BaseModel):
    meta: Meta
    profile: ProfileSummary
    horas: list[ScoredHora]
    dasha: list[DashaOut]  # dasha and bhukti periods overlapping the day; empty without dasha data
    top: TopWindows
    unverified_tables: list[str]


class RasiResponse(BaseModel):
    meta: Meta
    horas: list[HoraInfo]
    rasis: list[RasiRow]  # 12 rows, Mesha first; each has one cell per hora
    unverified_tables: list[str]


class ProfilesResponse(BaseModel):
    profiles: list[ProfileSummary]  # ids and display names only, never birth data


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    profiles: int


def _localise(value: Any, tz: Any) -> Any:
    if isinstance(value, datetime):
        # Whole seconds are plenty for panchangam times; keep neighbours' shared bounds equal.
        rounded = value.replace(microsecond=0) + timedelta(seconds=value.microsecond >= 500_000)
        return rounded.astimezone(tz)
    if isinstance(value, dict):
        return {k: _localise(v, tz) for k, v in value.items()}
    if isinstance(value, list):
        return [_localise(v, tz) for v in value]
    return value


def localise[M: BaseModel](model: M, tz: Any) -> M:
    """Rebuild `model` with every datetime converted to `tz` (internal values are UTC)."""
    return type(model).model_validate(_localise(model.model_dump(), tz))
