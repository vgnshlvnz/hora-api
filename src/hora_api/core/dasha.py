"""Vimshottari dasha and antardasha (bhukti) periods from the Moon's longitude at birth.

Pure calculation. The nakshatra the Moon was in decides the first dasha lord; how far through
the nakshatra it had travelled decides how much of that first dasha was already used up. Dasha
lengths come from data/vimshottari.yaml (passed in as a table). Year length is a parameter
(365.25 days by default).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal

from hora_api.core.astro import NAKSHATRA_SPAN
from hora_api.core.tables import DashaTable

DEFAULT_YEAR_DAYS: Final = 365.25
CYCLE_YEARS: Final = 120.0


@dataclass(frozen=True, slots=True)
class DashaSpan:
    lord: str
    level: Literal["maha", "antar"]
    start: datetime
    end: datetime


def nakshatra_lord(nakshatra: int, table: DashaTable) -> str:
    """Lord of the dasha a nakshatra (0-26) starts in."""
    return table.lords[nakshatra % 9]


def vimshottari(
    moon_longitude: float,
    birth: datetime,
    table: DashaTable,
    *,
    year_days: float = DEFAULT_YEAR_DAYS,
    horizon_years: float = CYCLE_YEARS,
) -> list[DashaSpan]:
    """Dasha and antardasha spans from `birth` for `horizon_years`, in time order.

    Each dasha is followed by its nine antardashas. The first dasha starts at birth (only its
    unused balance is listed, and so only the antardashas that end after birth). Times are UTC.
    """
    if birth.tzinfo is None or birth.utcoffset() is None:
        raise ValueError("birth must be timezone-aware")
    if year_days <= 0:
        raise ValueError("year_days must be positive")

    longitude = moon_longitude % 360.0
    nakshatra = min(int(longitude // NAKSHATRA_SPAN), 26)
    elapsed = (longitude - nakshatra * NAKSHATRA_SPAN) / NAKSHATRA_SPAN  # 0 <= elapsed < 1
    first = nakshatra % 9

    def at(years: float, origin: datetime) -> datetime:
        return origin + timedelta(days=years * year_days)

    origin = at(-table.years[first] * elapsed, birth)  # when the first dasha nominally began
    horizon = at(horizon_years, birth)
    spans: list[DashaSpan] = []
    years_done = 0.0
    k = 0
    while at(years_done, origin) < horizon:
        i = (first + k) % 9
        dasha_years = table.years[i]
        start, end = at(years_done, origin), at(years_done + dasha_years, origin)
        if end > birth:
            spans.append(DashaSpan(table.lords[i], "maha", max(start, birth), end))
            offset = years_done
            for j in range(9):
                a = (i + j) % 9
                bhukti_years = dasha_years * table.years[a] / CYCLE_YEARS
                a_start = at(offset, origin)
                a_end = end if j == 8 else at(offset + bhukti_years, origin)
                if a_end > birth:
                    spans.append(DashaSpan(table.lords[a], "antar", max(a_start, birth), a_end))
                offset += bhukti_years
        years_done += dasha_years
        k += 1
    return spans


def running(spans: list[DashaSpan], at: datetime) -> list[DashaSpan]:
    """The dasha and antardasha spans in force at `at`."""
    return [s for s in spans if s.start <= at < s.end]
