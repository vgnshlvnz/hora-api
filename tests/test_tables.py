import shutil
from pathlib import Path

import pytest

from hora_api.data.loader import (
    SCORING_TABLE_FILES,
    TABLE_FILES,
    default_data_dir,
    load_scoring_tables,
    load_tables,
)


def test_every_table_has_a_source_comment() -> None:
    for name in TABLE_FILES + SCORING_TABLE_FILES:
        path = default_data_dir() / f"{name}.yaml"
        first = next(ln for ln in path.read_text().splitlines() if ln.strip())
        assert first.startswith("# Source:"), path


def test_tables_load_with_expected_shape() -> None:
    t = load_tables()
    assert t.horas.chaldean_order == (
        "Saturn",
        "Jupiter",
        "Mars",
        "Sun",
        "Venus",
        "Mercury",
        "Moon",
    )
    assert t.horas.weekday_lords == ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
    assert len(t.varjyam.start_ghati) == 27
    assert len(t.kalams.rahu_kalam) == len(t.durmuhurta.day) == len(t.gowri.day) == 7
    assert all(len(row) == t.gowri.segments for row in t.gowri.day + t.gowri.night)


def test_unverified_tables_are_reported() -> None:
    unverified = load_tables().unverified
    assert {"durmuhurta", "varjyam", "gowri"} <= unverified
    assert "kalams" not in unverified and "horas" not in unverified


def test_missing_source_comment_is_rejected(tmp_path: Path) -> None:
    for name in TABLE_FILES:
        shutil.copy(default_data_dir() / f"{name}.yaml", tmp_path / f"{name}.yaml")
    kalams = tmp_path / "kalams.yaml"
    kalams.write_text(
        "\n".join(ln for ln in kalams.read_text().splitlines() if "Source:" not in ln)
    )
    with pytest.raises(ValueError, match="Source"):
        load_tables(tmp_path)


def test_scoring_tables_load_and_report_unverified() -> None:
    t = load_scoring_tables()
    assert len(t.names.nakshatras) == 27 and t.names.rasis[10] == "Kumbha"
    assert len(t.functional) == 12 and t.functional[10].yogakaraka == "Venus"
    assert "Jupiter" in t.friends["Sun"]
    assert t.unverified == {"functional", "hora_generic"}
    assert set(t.hora_generic) == set(t.names.planets)
