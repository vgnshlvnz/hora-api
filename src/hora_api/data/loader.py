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
    DashaTable,
    DurmuhurtaTable,
    GowriTable,
    HoraTable,
    KalamTable,
    Nature,
    Tables,
    VarjyamTable,
)
from hora_api.scoring.tables import (
    ChandraTable,
    FunctionalEntry,
    NameTable,
    Quality,
    ScoringTables,
    TaraTable,
)

WEEKDAYS: Final = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
TABLE_FILES: Final = ("horas", "kalams", "durmuhurta", "varjyam", "gowri", "vimshottari")
SCORING_TABLE_FILES: Final = (
    "names",
    "tarabala",
    "chandrabala",
    "functional",
    "friendship",
    "hora_generic",
)


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


def _start_ghatis(row: dict[str, Any]) -> tuple[float, ...]:
    """A varjyam row's `start_ghati` is one number, or a list when it has several windows."""
    raw = row["start_ghati"]
    values = tuple(float(x) for x in (raw if isinstance(raw, list) else [raw]))
    if not values:
        raise ValueError(f"varjyam.yaml: {row['name']} has no start_ghati")
    return values


def load_tables(data_dir: Path | None = None) -> Tables:
    root = data_dir or default_data_dir()
    docs = {name: _read(root, name) for name in TABLE_FILES}

    unverified: set[str] = {n for n, d in docs.items() if d.get("verify") is True}
    for name in ("durmuhurta", "gowri"):
        for day, row in docs[name]["weekdays"].items():
            if row.get("verify") is True:
                unverified.add(f"{name}:{day}")
    for row in docs["varjyam"]["nakshatras"]:
        if row.get("verify") is True:
            unverified.add(f"varjyam:{row['name']}")

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
        start_ghatis=tuple(_start_ghatis(n) for n in v["nakshatras"]),
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

    v2 = docs["vimshottari"]["sequence"]
    dasha = DashaTable(tuple(r["lord"] for r in v2), tuple(float(r["years"]) for r in v2))
    if len(dasha.lords) != 9 or sum(dasha.years) != 120:
        raise ValueError("vimshottari.yaml: expected nine lords whose years sum to 120")

    return Tables(horas, kalam, durm, varj, gow, dasha, frozenset(unverified))


def load_scoring_tables(data_dir: Path | None = None) -> ScoringTables:
    root = data_dir or default_data_dir()
    docs = {name: _read(root, name) for name in SCORING_TABLE_FILES}
    unverified = frozenset(n for n, d in docs.items() if d.get("verify") is True)

    n = docs["names"]
    names = NameTable(tuple(n["nakshatras"]), tuple(n["rasis"]), tuple(n["planets"]))
    if (len(names.nakshatras), len(names.rasis), len(names.planets)) != (27, 12, 7):
        raise ValueError("names.yaml: expected 27 nakshatras, 12 rasis, 7 planets")

    taras = sorted(docs["tarabala"]["taras"], key=lambda t: t["number"])
    if [t["number"] for t in taras] != list(range(1, 10)):
        raise ValueError("tarabala.yaml: expected taras numbered 1-9")
    tara = TaraTable(
        tuple(t["name"] for t in taras), tuple(cast("Quality", t["quality"]) for t in taras)
    )

    houses = docs["chandrabala"]["houses"]
    if sorted(houses) != list(range(1, 13)):
        raise ValueError("chandrabala.yaml: expected houses 1-12")
    chandra = ChandraTable(tuple(cast("Quality", houses[h]) for h in range(1, 13)))

    entries: dict[int, FunctionalEntry] = {}
    for row in docs["functional"]["lagnas"]:
        lagna = names.rasis.index(row["lagna"])
        entries[lagna] = FunctionalEntry(
            lagna=lagna,
            lagna_lord=row["lagna_lord"],
            yogakaraka=row["yogakaraka"],
            trikona_lords=frozenset(row["trikona_lords"]),
            dusthana_lords=frozenset(row["dusthana_lords"]),
            maraka_lords=frozenset(row["maraka_lords"]),
            neutral_lords=frozenset(row["neutral_lords"]),
        )
    if sorted(entries) != list(range(12)):
        raise ValueError("functional.yaml: expected one entry per lagna")

    friends = {p: frozenset(row["friends"]) for p, row in docs["friendship"]["planets"].items()}
    hora_generic = {p: float(v) for p, v in docs["hora_generic"]["lords"].items()}
    if set(hora_generic) != set(names.planets):
        raise ValueError("hora_generic.yaml: expected a value for each of the 7 planets")
    return ScoringTables(
        names,
        tara,
        chandra,
        tuple(entries[i] for i in range(12)),
        friends,
        hora_generic,
        unverified,
    )
