"""Computation behind the endpoints: cached panchangam days and recommended windows."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hora_api.api.keys import KeyStore
from hora_api.api.models import TopWindow, TopWindows
from hora_api.api.profiles import ProfileStore
from hora_api.api.settings import ApiSettings
from hora_api.core import astro
from hora_api.core import day as D
from hora_api.core.astro import Ayanamsa, Transition
from hora_api.core.day import Convention, Day, GowriSegment, Hora
from hora_api.core.tables import Tables
from hora_api.scoring.personal import ScoredHora
from hora_api.scoring.settings import ScoringSettings
from hora_api.scoring.tables import ScoringTables

CacheKey = tuple[date, float, float, str, Convention, Ayanamsa]


@dataclass(frozen=True, slots=True)
class RequestParams:
    date: date
    lat: float
    lon: float
    tz_name: str
    tz: ZoneInfo
    convention: Convention
    ayanamsa: Ayanamsa

    @property
    def key(self) -> CacheKey:
        return (self.date, self.lat, self.lon, self.tz_name, self.convention, self.ayanamsa)


@dataclass(frozen=True, slots=True)
class ComputedDay:
    day: Day
    horas: tuple[Hora, ...]
    gowri: tuple[GowriSegment, ...]
    transitions: tuple[Transition, ...]


class DayCache:
    """Thread-safe in-memory LRU of computed days."""

    def __init__(self, size: int) -> None:
        self._size = max(1, size)
        self._items: OrderedDict[CacheKey, ComputedDay] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: CacheKey) -> ComputedDay | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return item

    def put(self, key: CacheKey, item: ComputedDay) -> None:
        with self._lock:
            self._items[key] = item
            self._items.move_to_end(key)
            while len(self._items) > self._size:
                self._items.popitem(last=False)


@dataclass(slots=True)
class Services:
    settings: ApiSettings
    tables: Tables
    scoring_tables: ScoringTables
    scoring: ScoringSettings
    profiles: ProfileStore
    keys: KeyStore
    cache: DayCache


def compute_day(services: Services, p: RequestParams) -> ComputedDay:
    """The panchangam day for the request, from cache when possible.

    Raises ValueError if the sun does not rise or set at that place and date.
    """
    cached = services.cache.get(p.key)
    if cached is not None:
        return cached
    day = D.make_day(p.date, p.tz, p.lat, p.lon, p.ayanamsa)
    computed = ComputedDay(
        day=day,
        horas=tuple(D.build_horas(day, p.convention, services.tables)),
        gowri=tuple(D.gowri(day, services.tables)),
        transitions=tuple(astro.transitions(day.sunrise, day.next_sunrise, p.ayanamsa)),
    )
    services.cache.put(p.key, computed)
    return computed


def top_windows(scored: list[ScoredHora], day: Day, tz: ZoneInfo, min_minutes: int) -> TopWindows:
    """Best clean stretch overall, starting before local noon, and starting after sunset.

    A candidate is one clean part of a scored hora lasting at least `min_minutes`. Ties go to
    the higher score, then the longer stretch, then the earlier one.
    """
    noon = datetime.combine(day.date_local, time(12, 0), tzinfo=tz)
    candidates = [
        (s.score, part.end - part.start, part.start, TopWindow(
            start=part.start, end=part.end, lord=s.lord, score=s.score))
        for s in scored
        if s.score is not None
        for part in s.clean_parts
        if part.end - part.start >= timedelta(minutes=min_minutes)
    ]  # fmt: skip

    def best(pool: list[tuple[float, timedelta, datetime, TopWindow]]) -> TopWindow | None:
        if not pool:
            return None
        return min(pool, key=lambda c: (-c[0], -c[1].total_seconds(), c[2]))[3]

    return TopWindows(
        best_overall=best(candidates),
        best_before_noon=best([c for c in candidates if c[2] < noon]),
        best_after_sunset=best([c for c in candidates if c[2] >= day.sunset]),
    )
