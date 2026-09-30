"""Load the classical lookup tables from data/*.yaml into typed core tables.

This is the only place table files are read. Every file must start with a `# Source:` comment
and may carry `verify: true` (table level) or per-weekday `verify: true` rows; those are
collected in `Tables.unverified` so summaries can list them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, cast

import yaml

from hora_api.core.tables import (
    DurmuhurtaTable,
    GowriTable,
    HoraTable,
    KalamTable,
    Nature,
    Tables,
    VarjyamTable,
)

WEEKDAYS: Final = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
TABLE_FILES: Final = ("horas", "kalams", "durmuhurta", "varjyam", "gowri")


def default_data_dir() -> Path:
    """The repository's data/ directory (src layout: src/hora_api/data/loader.py)."""
    return Path(__file__).resolve().parents[3] / "data"


def _read(data_dir: Path, name: str) -> dict[str, Any]:
    path = data_dir / f"{name}.yaml"
    text = path.read_text(encoding="utf-8")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first.startswith("# Source:"):
        raise ValueError(f"{path}: must start with a '# Source:' comment")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a mapping at top level")
    return cast("dict[str, Any]", doc)


def _by_weekday(mapping: dict[str, Any], where: str) -> tuple[Any, ...]:
    missing = [d for d in WEEKDAYS if d not in mapping]
    if missing:
        raise ValueError(f"{where}: missing weekdays {missing}")
    return tuple(mapping[d] for d in WEEKDAYS)


def load_tables(data_dir: Path | None = None) -> Tables:
    root = data_dir or default_data_dir()
    docs = {name: _read(root, name) for name in TABLE_FILES}

    unverified: set[str] = {n for n, d in docs.items() if d.get("verify") is True}
    for name in ("durmuhurta", "gowri"):
        for day, row in docs[name]["weekdays"].items():
            if row.get("verify") is True:
                unverified.add(f"{name}:{day}")

    h = docs["horas"]
    order = tuple(h["chaldean_order"])
    horas = HoraTable(order, _by_weekday(h["weekday_lords"], "horas.weekday_lords"))
    if len(order) != 7 or set(horas.weekday_lords) - set(order):
        raise ValueError("horas.yaml: need 7 planets and weekday lords drawn from them")

    k = docs["kalams"]
    kalam = KalamTable(
        parts=int(k["parts"]),
        rahu_kalam=_by_weekday(k["rahu_kalam"], "kalams.rahu_kalam"),
        yamagandam=_by_weekday(k["yamagandam"], "kalams.yamagandam"),
        gulika_kalam=_by_weekday(k["gulika_kalam"], "kalams.gulika_kalam"),
    )

    d = docs["durmuhurta"]
    dw = _by_weekday(d["weekdays"], "durmuhurta.weekdays")
    durm = DurmuhurtaTable(
        parts=int(d["parts"]),
        day=tuple(tuple(int(n) for n in row["day"]) for row in dw),
        night=tuple(tuple(int(n) for n in row["night"]) for row in dw),
    )

    v = docs["varjyam"]
    if len(v["nakshatras"]) != 27:
        raise ValueError("varjyam.yaml: expected 27 nakshatras")
    varj = VarjyamTable(
        ghatikas_per_nakshatra=float(v["ghatikas_per_nakshatra"]),
        duration_ghatikas=float(v["duration_ghatikas"]),
        start_ghati=tuple(float(n["start_ghati"]) for n in v["nakshatras"]),
    )

    g = docs["gowri"]
    gw = _by_weekday(g["weekdays"], "gowri.weekdays")
    nature: dict[str, Nature] = {n: "good" for n in g["nature"]["good"]}
    nature.update({n: "bad" for n in g["nature"]["bad"]})
    seg = int(g["segments"])
    for row in gw:
        if (
            len(row["day"]) != seg
            or len(row["night"]) != seg
            or set(row["day"] + row["night"]) - set(nature)
        ):
            raise ValueError("gowri.yaml: rows must have `segments` known names each")
    gow = GowriTable(
        segments=seg,
        day=tuple(tuple(row["day"]) for row in gw),
        night=tuple(tuple(row["night"]) for row in gw),
        nature=nature,
    )

    return Tables(horas, kalam, durm, varj, gow, frozenset(unverified))
