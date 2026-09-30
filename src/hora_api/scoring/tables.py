"""Typed lookup tables for scoring. Values come from data/*.yaml via hora_api.data.loader."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Quality = Literal["good", "bad", "neutral", "conditional"]


@dataclass(frozen=True, slots=True)
class NameTable:
    nakshatras: tuple[str, ...]  # 27, Ashwini first
    rasis: tuple[str, ...]  # 12, Mesha first
    planets: tuple[str, ...]  # 7


@dataclass(frozen=True, slots=True)
class TaraTable:
    names: tuple[str, ...]  # 9, Janma first
    quality: tuple[Quality, ...]


@dataclass(frozen=True, slots=True)
class ChandraTable:
    quality: tuple[Quality, ...]  # 12, house 1 first


@dataclass(frozen=True, slots=True)
class FunctionalEntry:
    lagna: int  # 0-11
    lagna_lord: str
    yogakaraka: str | None
    trikona_lords: frozenset[str]
    dusthana_lords: frozenset[str]
    maraka_lords: frozenset[str]
    neutral_lords: frozenset[str]


@dataclass(frozen=True, slots=True)
class ScoringTables:
    names: NameTable
    tara: TaraTable
    chandra: ChandraTable
    functional: tuple[FunctionalEntry, ...]  # indexed by lagna
    friends: dict[str, frozenset[str]]  # planet -> natural friends
    unverified: frozenset[str]
