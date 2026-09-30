"""Rasi matrix: every rasi against every hora of a day, by chandrabala alone.

For each of the 12 rasis the janma rasi is taken to be that rasi. There is no lagna and no
tarabala. The universal hard filters apply (Rahu kalam, Yamagandam, Gulika kalam, Durmuhurta,
Varjyam), and so does Chandrashtama for that rasi. The hora lord contributes only through the
generic table data/hora_generic.yaml, and only if ScoringSettings.rasi_hora_generic is on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import AwareDatetime, BaseModel

from hora_api.core import astro
from hora_api.core.day import Day, Hora, blocked_windows, clean_parts
from hora_api.core.tables import Tables
from hora_api.scoring.personal import (
    ChandraChange,
    ChandraDetail,
    _default_tables,
    chandra_value,
    chandrabala,
    majority_piece,
    moon_pieces,
)
from hora_api.scoring.settings import ScoringSettings
from hora_api.scoring.tables import ScoringTables


@dataclass(frozen=True, slots=True)
class _RasiRef:
    janma_rasi: int


class HoraInfo(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    lord: str
    is_night: bool


class RasiCell(BaseModel):
    score: float | None  # None when the hora is fully blocked for this rasi
    clean_seconds: float
    blocked_reasons: list[str]
    chandra: ChandraDetail  # value covering the majority of the hora's clean time
    chandra_change: ChandraChange | None = None


class RasiRow(BaseModel):
    rasi: int  # 0-11, Mesha first
    name: str
    cells: list[RasiCell]  # one per hora, in the order of RasiMatrix.horas
    # Mean of the hora scores weighted by clean time (None if the whole day is blocked).
    day_percent: float | None
    # Share of the day (sunrise to next sunrise) that survives the hard filters, 0-100.
    clean_percent: float


class RasiMatrix(BaseModel):
    horas: list[HoraInfo]
    rasis: list[RasiRow]  # 12 rows, Mesha first


def score_rasis(
    horas: Sequence[Hora],
    day: Day,
    tables: Tables,
    settings: ScoringSettings | None = None,
    scoring_tables: ScoringTables | None = None,
) -> RasiMatrix:
    """Score all `horas` for each of the 12 rasis."""
    cfg = settings or ScoringSettings()
    st = scoring_tables or _default_tables()

    w_hora = cfg.rasi_weight_hora if cfg.rasi_hora_generic else 0.0
    scale = 100.0 / (cfg.rasi_weight_chandra + w_hora)
    day_seconds = (day.next_sunrise - day.sunrise).total_seconds()

    rows: list[RasiRow] = []
    for rasi in range(12):
        blocked = blocked_windows(day, tables, _RasiRef(rasi))
        cells: list[RasiCell] = []
        weighted = 0.0
        clean_total = 0.0
        for hora in horas:
            clean = clean_parts(hora, blocked)
            clean_seconds = sum(c.duration.total_seconds() for c in clean)
            reasons = sorted(
                {r for w in blocked if w.start < hora.end and w.end > hora.start for r in w.reasons}
            )

            pieces = moon_pieces(hora, day.rasi_spans)
            paksha = astro.paksha(hora.start)  # judged at the start of the hora
            chandras = [chandrabala(rasi, i, st, paksha) for i, _, _ in pieces]
            used = majority_piece(pieces, clean, hora)
            change = (
                ChandraChange(at=pieces[1][1], before=chandras[0], after=chandras[-1])
                if len(chandras) > 1
                else None
            )

            points = cfg.rasi_weight_chandra * chandra_value(chandras[used], cfg) * scale
            if w_hora:
                points += w_hora * st.hora_generic[hora.lord] * scale
            score = round(points, 1) if clean else None
            if clean:
                weighted += points * clean_seconds
                clean_total += clean_seconds

            cells.append(
                RasiCell(
                    score=score,
                    clean_seconds=clean_seconds,
                    blocked_reasons=reasons,
                    chandra=chandras[used],
                    chandra_change=change,
                )
            )
        rows.append(
            RasiRow(
                rasi=rasi,
                name=st.names.rasis[rasi],
                cells=cells,
                day_percent=round(weighted / clean_total, 1) if clean_total else None,
                clean_percent=round(100.0 * clean_total / day_seconds, 1),
            )
        )

    return RasiMatrix(
        horas=[HoraInfo(start=h.start, end=h.end, lord=h.lord, is_night=h.is_night) for h in horas],
        rasis=rows,
    )
