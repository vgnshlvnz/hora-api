"""rasi-scoring tests: 12 x 24 matrix on the PJ day (Wed 2026-09-30, tamil)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from hora_api.core import day as D
from hora_api.data.loader import load_tables
from hora_api.scoring.rasi import RasiMatrix, RasiRow, score_rasis
from hora_api.scoring.settings import ScoringSettings

KL = ZoneInfo("Asia/Kuala_Lumpur")
TABLES = load_tables()
PJ = D.make_day(date(2026, 9, 30), KL, 3.107, 101.606)
HORAS = D.build_horas(PJ, "tamil", TABLES)
MATRIX = score_rasis(HORAS, PJ, TABLES)
KANYA, TULA = 5, 6


def row(matrix: RasiMatrix, name: str) -> RasiRow:
    return next(r for r in matrix.rasis if r.name == name)


def hhmm(t: datetime) -> str:
    return (t.astimezone(KL) + timedelta(seconds=30)).strftime("%H:%M")


def test_matrix_shape_and_ordering() -> None:
    assert len(MATRIX.rasis) == 12 and len(MATRIX.horas) == 24
    assert [r.rasi for r in MATRIX.rasis] == list(range(12))
    assert [r.name for r in MATRIX.rasis][:3] == ["Mesha", "Vrishabha", "Mithuna"]
    assert MATRIX.rasis[-1].name == "Meena"
    assert all(len(r.cells) == 24 for r in MATRIX.rasis)
    # Horas are in time order, identical to the input, and each row lines up with them.
    assert [(h.start, h.end, h.lord) for h in MATRIX.horas] == [
        (h.start, h.end, h.lord) for h in HORAS
    ]
    assert [hhmm(h.start) for h in MATRIX.horas][:3] == ["07:02", "08:02", "09:02"]
    assert MATRIX.horas[0].lord == "Mercury" and MATRIX.horas[-1].lord == "Saturn"


def test_kanya_and_tula_chandrashtama() -> None:
    """Kanya is in Chandrashtama until ~15:44 (Moon in Mesha is 8th from Kanya); Tula from ~15:44.

    Count on the PJ day: Kanya's Chandrashtama touches 9 of the 24 horas (07:02-15:02), 8 of
    them fully blocked (the 15:02 hora keeps 15:44-16:02). Tula's touches 16 horas (15:02-06:02,
    the 15:02 hora keeps 15:02-15:44); 15 of them have no clean part, plus 09:02, 12:02 and 13:02
    blocked for everyone, so 18 Tula horas score None.
    """
    kanya, tula = row(MATRIX, "Kanya"), row(MATRIX, "Tula")
    k_hit = [i for i, c in enumerate(kanya.cells) if "chandrashtama" in c.blocked_reasons]
    t_hit = [i for i, c in enumerate(tula.cells) if "chandrashtama" in c.blocked_reasons]
    assert k_hit == list(range(0, 9)) and t_hit == list(range(8, 24))
    assert len(k_hit) == 9 and len(t_hit) == 16
    assert sum(c.score is None for c in kanya.cells[:8]) == 8
    assert kanya.cells[8].score is not None and tula.cells[8].score is not None
    assert sum(c.score is None for c in tula.cells) == 18
    # The moon leaves Mesha at ~15:44, inside the 15:02 hora.
    change = kanya.cells[8].chandra_change
    assert change is not None and hhmm(change.at) in {"15:44", "15:43", "15:45"}
    assert (change.before.house, change.after.house) == (8, 9)
    # No other rasi is in Chandrashtama today.
    others = [r for r in MATRIX.rasis if r.name not in {"Kanya", "Tula"}]
    assert all("chandrashtama" not in c.blocked_reasons for r in others for c in r.cells)


def test_universal_filters_hit_every_rasi() -> None:
    for r in MATRIX.rasis:
        for i in (2, 5, 6):  # 09:02 Yamagandam, 12:02 Gulika+Durmuhurta, 13:02 Gulika+Rahu
            assert r.cells[i].score is None, (r.name, i)
    a = [c.blocked_reasons for c in row(MATRIX, "Karka").cells]
    assert a[2] == ["yamagandam"] and "rahu_kalam" in a[6]


def test_scores_are_chandrabala_only_by_default() -> None:
    scores = {c.score for r in MATRIX.rasis for c in r.cells if c.score is not None}
    assert scores <= {0.0, 50.0, 100.0}  # good / conditional / bad; hora lord plays no part
    vrishabha = row(MATRIX, "Vrishabha")
    assert vrishabha.cells[0].chandra.house == 12 and vrishabha.cells[0].score == 0.0
    assert vrishabha.cells[10].chandra.house == 1 and vrishabha.cells[10].score == 100.0
    # Same rasi, same Moon: a good hora lord and a bad one score alike.
    assert vrishabha.cells[10].score == vrishabha.cells[11].score  # Saturn, Jupiter


def test_generic_hora_lord_term_is_optional() -> None:
    on = score_rasis(HORAS, PJ, TABLES, ScoringSettings(rasi_hora_generic=True))
    v = row(on, "Vrishabha")
    # 16:02 Saturn (0.0) and 17:02 Jupiter (1.0) with the Moon in the 1st house (good).
    assert on.horas[9].lord == "Saturn" and v.cells[9].score == 50.0
    assert on.horas[10].lord == "Jupiter" and v.cells[10].score == 100.0
    weights = ScoringSettings(rasi_hora_generic=True, rasi_weight_hora=0.0)
    assert score_rasis(HORAS, PJ, TABLES, weights).rasis[1].cells[10].score == 100.0


def test_day_percent_is_clean_time_weighted_mean() -> None:
    for r in MATRIX.rasis:
        pairs = [(c.score, c.clean_seconds) for c in r.cells if c.score is not None]
        total = sum(w for _, w in pairs)
        expected = sum(s * w for s, w in pairs) / total
        assert r.day_percent == pytest.approx(expected, abs=0.2)  # cells are rounded to 0.1
    assert row(MATRIX, "Karka").day_percent == 100.0
    assert row(MATRIX, "Kanya").day_percent == 50.0
    assert row(MATRIX, "Tula").day_percent == 100.0
    assert row(MATRIX, "Kanya").clean_percent < row(MATRIX, "Karka").clean_percent
    assert row(MATRIX, "Tula").clean_percent == pytest.approx(17.4, abs=0.1)
    assert all(0.0 <= r.clean_percent <= 100.0 for r in MATRIX.rasis)


def test_moon_change_reported_per_row() -> None:
    mesha = row(MATRIX, "Mesha").cells[8]  # 15:02 hora: Moon leaves Mesha at ~15:44
    assert mesha.chandra_change is not None
    assert (mesha.chandra_change.before.house, mesha.chandra_change.after.house) == (1, 2)
    assert row(MATRIX, "Mesha").cells[0].chandra_change is None


def test_conditional_houses_follow_paksha_in_the_matrix() -> None:
    # 2026-09-22 is shukla: houses 2, 5 and 9 score 100 (they scored 50 with one value).
    day = D.make_day(date(2026, 9, 22), KL, 3.107, 101.606)
    horas = D.build_horas(day, "tamil", TABLES)
    shukla = score_rasis(horas, day, TABLES)
    flat = score_rasis(horas, day, TABLES, ScoringSettings(chandra_paksha=False))
    moon_rasi = day.rasi_spans[0].index  # Makara (9) for the whole day
    assert len(day.rasi_spans) == 1
    for row_s, row_f in zip(shukla.rasis, flat.rasis, strict=True):
        house = (moon_rasi - row_s.rasi) % 12 + 1
        cell_s, cell_f = row_s.cells[1], row_f.cells[1]  # the 08:02 hora
        if house in (2, 5, 9):
            assert cell_s.chandra.paksha == "shukla"
            if cell_s.score is not None and cell_f.score is not None:
                assert (cell_s.score, cell_f.score) == (100.0, 50.0)
        else:
            assert cell_s.chandra.paksha is None and cell_s.score == cell_f.score
