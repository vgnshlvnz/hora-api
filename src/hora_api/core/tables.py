"""Typed lookup tables consumed by the pure calculation code.

The values come from data/*.yaml; loading (I/O) lives in hora_api.data, never here.
Weekday indices are 0 = Sunday ... 6 = Saturday everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Nature = Literal["good", "bad"]


@dataclass(frozen=True, slots=True)
class HoraTable:
    chaldean_order: tuple[str, ...]  # 7 planets
    weekday_lords: tuple[str, ...]  # 7, Sunday first


@dataclass(frozen=True, slots=True)
class KalamTable:
    parts: int
    rahu_kalam: tuple[int, ...]  # 1-based segment per weekday
    yamagandam: tuple[int, ...]
    gulika_kalam: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DurmuhurtaTable:
    parts: int
    day: tuple[tuple[int, ...], ...]  # per weekday: 1-based day muhurta numbers
    night: tuple[tuple[int, ...], ...]  # per weekday: 1-based night muhurta numbers


@dataclass(frozen=True, slots=True)
class VarjyamTable:
    ghatikas_per_nakshatra: float
    duration_ghatikas: float
    start_ghati: tuple[float, ...]  # 27 entries, Ashwini first


@dataclass(frozen=True, slots=True)
class GowriTable:
    segments: int
    day: tuple[tuple[str, ...], ...]  # per weekday: segment names in order
    night: tuple[tuple[str, ...], ...]
    nature: dict[str, Nature]


@dataclass(frozen=True, slots=True)
class Tables:
    horas: HoraTable
    kalams: KalamTable
    durmuhurta: DurmuhurtaTable
    varjyam: VarjyamTable
    gowri: GowriTable
    unverified: frozenset[str]  # names of tables (or "table:weekday" rows) marked verify: true
