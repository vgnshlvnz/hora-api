"""personal-scoring tests: golden profile on the PJ day (Wed 2026-09-30, tamil)."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from hora_api.core import day as D
from hora_api.core.day import Day, Hora, MoonSpan
from hora_api.data.loader import load_scoring_tables, load_tables
from hora_api.scoring import personal as P
from hora_api.scoring.settings import ScoringSettings

KL = ZoneInfo("Asia/Kuala_Lumpur")
TABLES = load_tables()
STABLES = load_scoring_tables()
FIXTURE: dict[str, Any] = yaml.safe_load(
    (Path(__file__).parent / "fixtures" / "golden.yaml").read_text()
)
GOLDEN = P.Profile(**FIXTURE["profile"])
ROHINI, MESHA, VRISHABHA, KANYA, KUMBHA = 3, 0, 1, 5, 10

PJ = D.make_day(date(2026, 9, 30), KL, 3.107, 101.606)
HORAS = D.build_horas(PJ, "tamil", TABLES)


def hhmm(t: datetime) -> str:
    return (t.astimezone(KL) + timedelta(seconds=30)).strftime("%H:%M")


def by_start(scored: list[P.ScoredHora]) -> dict[str, P.ScoredHora]:
    return {hhmm(s.start): s for s in scored}


def minutes_from(t: datetime, hh: int, mm: int) -> float:
    target = t.astimezone(KL).replace(hour=hh, minute=mm, second=0, microsecond=0)
    return abs((t.astimezone(KL) - target).total_seconds()) / 60


# ---------------------------------------------------------------------------
# Golden
# ---------------------------------------------------------------------------


def test_golden_profile_fixture() -> None:
    assert (GOLDEN.janma_nakshatra, GOLDEN.janma_rasi, GOLDEN.lagna) == (ROHINI, VRISHABHA, KUMBHA)


def test_derive_profile_matches_golden() -> None:
    birth = FIXTURE["birth"]
    derived = P.derive_profile(
        datetime.fromisoformat(birth["datetime"]),
        birth["lat"],
        birth["lon"],
        id="golden",
        display_name="Golden (fixture)",
        tz_home="Asia/Kuala_Lumpur",
    )
    assert derived == GOLDEN


def test_golden_hora_ranks() -> None:
    ranks = P.hora_lord_ranks(KUMBHA)
    assert ranks == {
        "Venus": 3, "Saturn": 3, "Mercury": 2, "Jupiter": 1, "Mars": 1, "Sun": 0, "Moon": 0,
    }  # fmt: skip


def test_golden_scores() -> None:
    s = by_start(P.score_horas(HORAS, PJ, GOLDEN, TABLES))
    assert round(s["07:02"].score or -1) == 58 and s["07:02"].lord == "Mercury"
    assert round(s["16:02"].score or -1) == 100 and s["16:02"].lord == "Saturn"
    assert round(s["20:02"].score or -1) == 100 and s["20:02"].lord == "Venus"
    assert round(s["21:02"].score or -1) == 83 and s["21:02"].lord == "Mercury"
    for blocked in ("09:02", "13:02"):
        assert s[blocked].score is None and s[blocked].clean_parts == []
        assert s[blocked].blocked_reasons


def test_golden_components_add_up() -> None:
    s = by_start(P.score_horas(HORAS, PJ, GOLDEN, TABLES))["07:02"]
    c = s.components
    assert (c.tara, c.chandra, c.hora, c.dasha) == (25.0, 0.0, 33.3, None)
    assert s.tara.name == "Mitra" and s.chandra.house == 12 and s.hora_rank == 2


def test_golden_tara_and_chandra_changes() -> None:
    """The brief says ~10:17 and ~15:47; verified ephemeris times are 10:07 and 15:44."""
    scored = by_start(P.score_horas(HORAS, PJ, GOLDEN, TABLES))
    jupiter = scored["10:02"]
    assert jupiter.tara_change is not None
    assert (jupiter.tara_change.before.name, jupiter.tara_change.after.name) == (
        "Mitra",
        "Parama Mitra",
    )
    assert minutes_from(jupiter.tara_change.at, 10, 7) <= 2
    assert jupiter.tara.name == "Parama Mitra"  # clean time is all after the change
    assert jupiter.chandra_change is None

    moon = scored["15:02"]
    assert moon.chandra_change is not None
    assert (moon.chandra_change.before.house, moon.chandra_change.after.house) == (12, 1)
    assert minutes_from(moon.chandra_change.at, 15, 44) <= 2
    assert moon.chandra.house == 12  # 42 of 60 minutes are before the change


def test_golden_tara_and_chandra_over_the_day() -> None:
    scored = by_start(P.score_horas(HORAS, PJ, GOLDEN, TABLES))
    assert scored["07:02"].tara.name == "Mitra" and scored["12:02"].tara.name == "Parama Mitra"
    assert scored["12:02"].chandra.house == 12 and scored["16:02"].chandra.house == 1


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


def test_tarabala_formula_and_names() -> None:
    assert P.tarabala(ROHINI, 1).name == "Mitra" and P.tarabala(ROHINI, 1).number == 8
    assert P.tarabala(ROHINI, 2).name == "Parama Mitra"
    assert (P.tarabala(ROHINI, ROHINI).number, P.tarabala(ROHINI, ROHINI).name) == (1, "Janma")
    assert P.tarabala(ROHINI, 4).name == "Sampat"
    assert P.tarabala(26, 0).number == 2  # wraps: count 2
    assert P.tarabala(0, 9).number == 1  # count 10 -> tara 1 again
    good = {n for n in range(1, 10) if P.tarabala(0, n - 1).quality == "good"}
    assert good == {2, 4, 6, 8, 9}
    assert {P.tarabala(0, n - 1).number for n in (3, 5, 7)} == {3, 5, 7}
    assert all(P.tarabala(0, n - 1).quality == "bad" for n in (3, 5, 7))


@given(janma=st.integers(0, 26), day=st.integers(0, 26))
def test_tarabala_range(janma: int, day: int) -> None:
    t = P.tarabala(janma, day)
    assert 1 <= t.number <= 9
    assert t.number == ((((day - janma) % 27) + 1 - 1) % 9) + 1


def test_chandrabala_houses() -> None:
    assert P.chandrabala(VRISHABHA, MESHA).house == 12
    assert P.chandrabala(VRISHABHA, VRISHABHA).house == 1
    assert P.chandrabala(KANYA, MESHA).house == 8
    qualities = {h: P.chandrabala(0, h - 1).quality for h in range(1, 13)}
    assert {h for h, q in qualities.items() if q == "good"} == {1, 3, 6, 7, 10, 11}
    assert {h for h, q in qualities.items() if q == "bad"} == {4, 8, 12}
    assert {h for h, q in qualities.items() if q == "conditional"} == {2, 5, 9}


def test_hora_rank_is_derived_not_hardcoded() -> None:
    # Different lagnas give different ranks from the same rule and table.
    assert P.hora_lord_rank(KUMBHA, "Venus") == 3
    assert P.hora_lord_rank(0, "Mars") == 3  # Mesha: lagna lord
    assert P.hora_lord_rank(3, "Mars") == 3  # Karka: yogakaraka
    assert P.hora_lord_rank(1, "Saturn") == 3  # Vrishabha: yogakaraka
    for lagna in range(12):
        ranks = P.hora_lord_ranks(lagna)
        assert set(ranks.values()) <= {0, 1, 2, 3}
        assert ranks[STABLES.functional[lagna].lagna_lord] == 3


def test_settings_change_scores() -> None:
    base = by_start(P.score_horas(HORAS, PJ, GOLDEN, TABLES))["07:02"]
    heavy = ScoringSettings(weight_hora=100.0)
    s = by_start(P.score_horas(HORAS, PJ, GOLDEN, TABLES, heavy))["07:02"]
    assert base.score == 58.3 and s.score != base.score
    # (25*1 + 25*0 + 100*2/3) / 150 * 100
    assert s.score == pytest.approx(61.1, abs=0.1)

    cond = replace(STABLES.chandra, quality=("conditional",) * 12)
    tables = replace(STABLES, chandra=cond)
    lenient = ScoringSettings(chandra_conditional_value=1.0)
    out = by_start(P.score_horas(HORAS, PJ, GOLDEN, TABLES, lenient, tables))["07:02"]
    assert out.components.chandra == 25.0


def test_dasha_component() -> None:
    def period(lord: str, level: str = "maha") -> dict[str, Any]:
        return {
            "lord": lord, "level": level,
            "start": datetime(2020, 1, 1, tzinfo=UTC), "end": datetime(2030, 1, 1, tzinfo=UTC),
        }  # fmt: skip

    profile = GOLDEN.model_copy(update={"dasha": [P.DashaPeriod(**period("Venus"))]})
    scored = by_start(P.score_horas(HORAS, PJ, profile, TABLES))
    saturn, venus, moon = scored["16:02"], scored["20:02"], scored["23:02"]
    assert venus.components.dasha == pytest.approx(16.7, abs=0.1)  # dasha lord: full 20/120
    assert saturn.components.dasha == pytest.approx(8.3, abs=0.1)  # natural friend: half
    assert scored["19:02"].components.dasha == 0.0  # Sun is an enemy of Venus
    assert venus.score == 100.0
    assert saturn.score == pytest.approx(91.7, abs=0.1)  # (100 + 10) / 120
    assert moon.lord == "Saturn"

    bhukti = profile.model_copy(update={"dasha": [P.DashaPeriod(**period("Mars", "antar"))]})
    m = by_start(P.score_horas(HORAS, PJ, bhukti, TABLES))["11:02"]
    assert m.lord == "Mars" and m.components.dasha == pytest.approx(16.7, abs=0.1)

    expired = P.DashaPeriod(
        lord="Venus", start=datetime(2020, 1, 1, tzinfo=UTC), end=datetime(2021, 1, 1, tzinfo=UTC)
    )
    none_running = GOLDEN.model_copy(update={"dasha": [expired]})
    v = by_start(P.score_horas(HORAS, PJ, none_running, TABLES))["20:02"]
    assert v.components.dasha == 0.0


def test_chandrashtama_blocks_scoring() -> None:
    kanya = GOLDEN.model_copy(update={"janma_rasi": KANYA})
    scored = by_start(P.score_horas(HORAS, PJ, kanya, TABLES))
    for key in ("07:02", "08:02", "09:02", "10:02", "11:02", "12:02", "13:02", "14:02"):
        assert scored[key].score is None, key
        assert "chandrashtama" in scored[key].blocked_reasons
    assert scored["15:02"].clean_parts  # Moon leaves Mesha at 15:44, so the tail is clean
    assert scored["16:02"].score is not None


def test_majority_of_clean_time_decides() -> None:
    """Chandra changes at 06:40 in a 06:00-07:00 hora; the first part is Chandrashtama."""
    sunrise = datetime(2026, 9, 27, 6, 0, tzinfo=UTC)  # a Sunday
    change = sunrise + timedelta(minutes=40)
    day = Day(
        date_local=date(2026, 9, 27), weekday=0, sunrise=sunrise,
        sunset=sunrise + timedelta(hours=12), next_sunrise=sunrise + timedelta(hours=24),
        nakshatra_spans=(MoonSpan(3, sunrise - timedelta(hours=5), sunrise + timedelta(hours=20)),),
        rasi_spans=(
            MoonSpan(MESHA, sunrise, change),
            MoonSpan(VRISHABHA, change, sunrise + timedelta(hours=24)),
        ),
    )  # fmt: skip
    hora = Hora(sunrise, sunrise + timedelta(hours=1), "Sun", False)
    kanya = GOLDEN.model_copy(update={"janma_rasi": KANYA})  # Mesha is 8th: blocked until 06:40
    (kanya_out,) = P.score_horas([hora], day, kanya, TABLES)
    assert (
        kanya_out.chandra.house == 9 and kanya_out.chandra_change is not None
    )  # after: 9th from Kanya
    assert (kanya_out.chandra_change.before.house, kanya_out.chandra_change.after.house) == (8, 9)
    # A profile with no block: 40 of 60 minutes are before the change, so "before" wins.
    (plain,) = P.score_horas([hora], day, GOLDEN, TABLES)
    assert plain.chandra.house == 12 and plain.chandra_change is not None


# ---------------------------------------------------------------------------
# Profile model
# ---------------------------------------------------------------------------


def test_profile_accepts_names_or_indices() -> None:
    p = P.Profile.model_validate(
        {
            "id": "x", "display_name": "X", "janma_nakshatra": "purva phalguni",
            "janma_rasi": 4, "lagna": "Meena", "tz_home": "UTC",
        }
    )  # fmt: skip
    assert (p.janma_nakshatra, p.janma_rasi, p.lagna) == (10, 4, 11)


def test_profile_validation() -> None:
    ok: dict[str, Any] = {**FIXTURE["profile"]}
    with pytest.raises(ValidationError, match="unknown nakshatra"):
        P.Profile(**{**ok, "janma_nakshatra": "Nowhere"})
    with pytest.raises(ValidationError):
        P.Profile(**{**ok, "lagna": 12})
    with pytest.raises(ValidationError, match="IANA"):
        P.Profile(**{**ok, "tz_home": "Mars/Olympus"})
    with pytest.raises(ValidationError):
        P.Profile(
            **{
                **ok,
                "dasha": [
                    {"lord": "Sun", "start": "2020-01-01T00:00:00", "end": "2021-01-01T00:00:00"}
                ],
            }
        )


# ---------------------------------------------------------------------------
# One code path for any profile
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(nak=st.integers(0, 26), rasi=st.integers(0, 11), lagna=st.integers(0, 11))
def test_any_profile_scores_consistently(nak: int, rasi: int, lagna: int) -> None:
    profile = P.Profile(
        id="p", display_name="P", janma_nakshatra=nak, janma_rasi=rasi, lagna=lagna, tz_home="UTC"
    )
    scored = P.score_horas(HORAS, PJ, profile, TABLES)
    assert len(scored) == 24
    for s in scored:
        assert (s.score is None) == (not s.clean_parts)
        if s.score is not None:
            assert 0.0 <= s.score <= 100.0
            c = s.components
            assert s.score == pytest.approx(c.tara + c.chandra + c.hora, abs=0.2)
