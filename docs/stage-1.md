# Stage 1: query API

Version 0.1.0. A Python HTTP API that answers "which horas and time windows are favourable for a
given person, date and place".

## What it does

For a date and place it computes a panchangam-style day: sunrise, sunset, next sunrise, and the
nakshatra, rasi and tithi transitions. It divides the day (sunrise to next sunrise) into 24
horas under one of two conventions, removes inauspicious windows, and scores what is left
against a person's natal data.

- **Zodiac:** sidereal. Ayanamsa is `lahiri` (default) or `kp`.
- **Hora conventions:** `tamil` (default; 60-minute slots from sunrise, the last one ending at
  next sunrise) or `classical` (day length / 12, then night length / 12). Lords follow the
  Chaldean order starting from the weekday lord.
- **Hard filters** (a window is removed, never merely penalised): Rahu kalam, Yamagandam, Gulika
  kalam, Durmuhurta, Varjyam, and Chandrashtama for the person.
- **Personal score (0-100):** tarabala + chandrabala + hora-lord rank from the natal lagna, plus
  an optional dasha match. Weights are settings (`HORA_SCORING_*`), normalised over the active
  components. Fully blocked horas score `null`.
- **Gowri panchangam** (Nalla Neram) is a separate layer in `/v1/day` and is never blended into
  any score.
- **Rasi matrix:** every rasi against every hora by chandrabala alone, plus the hard filters.

All datetimes are timezone-aware. Calculation is in UTC; output is in the request's IANA
timezone, rounded to whole seconds.

## Run it locally

```
make install
make hooks      # once per clone
make check      # ruff, mypy --strict, pytest
make run        # http://127.0.0.1:8000, docs at /v1/docs
```

Configuration, all optional, from the environment:

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `PROFILES_PATH` | `~/.config/hora-api/profiles.yaml` | Profiles file, kept outside the repo |
| `API_KEYS` | empty | Comma-separated keys; empty turns auth off, otherwise send `X-API-Key` |
| `DEFAULT_LAT`, `DEFAULT_LON`, `DEFAULT_TZ` | Petaling Jaya | Used when a request omits them |
| `CACHE_SIZE` | 128 | In-memory LRU of computed days |
| `MIN_WINDOW_MINUTES` | 15 | Shortest clean stretch reported as a top window |
| `DATA_DIR` | repo `data/` | Directory holding the lookup tables |
| `HORA_SCORING_*` | see `scoring/settings.py` | Scoring weights and quality values |

Profiles file format (names or indices are accepted; never put birth details in it):

```yaml
profiles:
  - id: me
    display_name: Me
    janma_nakshatra: Rohini
    janma_rasi: Vrishabha
    lagna: Kumbha
    tz_home: Asia/Kuala_Lumpur
```

## Endpoints

All under `/v1` unless noted. JSON in and out; errors are RFC 9457 `application/problem+json`.
OpenAPI: `/v1/openapi.json`. Common query parameters: `date`, `lat`, `lon`, `tz`, `convention`,
`ayanamsa`.

| Endpoint | Returns |
| -------- | ------- |
| `GET /v1/day` | Sun events, transitions, horas, blocked windows, Gowri layer |
| `GET /v1/horas/personal?profile_id=` | Scored horas and the top windows (best overall, before noon, after sunset) |
| `POST /v1/horas/personal` | Same for an inline `Profile` body; nothing is stored |
| `GET /v1/horas/rasi` | 12 x 24 matrix and per-rasi percentages |
| `GET /v1/profiles` | Ids and display names only, never birth data |
| `GET /healthz`, `GET /readyz` | Liveness; readiness (ephemeris answers, profiles load) |

Each scoring/day response also lists `unverified_tables`: the tables it used that are marked
`verify: true`.

The reference run for the golden Petaling Jaya day (Wed 2026-09-30, Lahiri, tamil) is saved in
`docs/golden/2026-09-30-pj.json`, holding `/v1/day`, `/v1/horas/personal` for the synthetic
`golden` profile, and `/v1/horas/rasi`. Regenerate it by starting the app with a profiles file
containing `tests/fixtures/golden.yaml`'s `profile` entry and saving those three responses for
the request parameters recorded at the top of the file.

## Known limitations

- **Golden transition times differ from the brief.** The brief quoted about 10:17, 15:47 and
  17:32 for the nakshatra, rasi and tithi changes on the golden day. Swiss Ephemeris gives 10:07,
  15:44 and 17:26, and PyEphem agrees with those to well under a minute. The tests use the
  verified times. Sunrise, sunset and everything else in the golden day match the brief.
- **Several tables are unverified** (list below). No table was checked against a primary text.
  Source comments name texts (BPHS chapters, Muhurta Chintamani, Drik Panchang) from memory, so
  treat those citations as pointers to check, including for tables marked `verify: false`. Only
  the values supplied in the brief (horas, kalams, tara and chandra classes, and the Kumbha
  ranks the functional table has to reproduce) came from the requirements.
- **Hora-lord rank rule is a project convention.** BPHS gives functional nature, not a numeric
  rank. The precedence (yogakaraka or lagna lord 3, trikona lord 2, lord of a house 3, 4, 10 or
  11 gets 1, dusthana or maraka lords only 0) was chosen to reproduce the Kumbha reference ranks.
- **Dasha periods are input, not computed.** There is no Vimshottari calculation. Profiles that
  carry periods get a dasha component (default weight 20); others get none.
- **Chandrabala houses 2, 5 and 9** share one configurable value. There is no shukla-paksha
  dependent mode.
- **`hora_generic` (rasi matrix hora-lord term) is a placeholder** with no source. It is off by
  default.
- **Rasi `day_percent`** is the mean of hora scores weighted by clean time, so blocked time does
  not lower it. `clean_percent` gives the share of the day that survives the filters.
- **Tamil `is_night`** is true when a slot's midpoint is after sunset.
- **`tz` defines the local date.** A `tz` far from the place makes the "day" start at that zone's
  midnight, so it can begin at a later sunrise than expected.
- **Profiles assume the request's ayanamsa.** Stored nakshatra/rasi/lagna are not recomputed if
  a request asks for a different ayanamsa than the one they were derived with.
- **`DATA_DIR` does not affect name resolution** of profile fields (for example "Rohini"), which
  always reads the repo's `data/names.yaml`.
- **No sunrise or sunset** (polar latitudes) returns a 422 problem.
- **Ephemeris:** the built-in Moshier ephemeris is used, so no data files are needed. Swiss
  Ephemeris is dual-licensed (AGPL or a commercial licence); check that before distributing or
  hosting.
- **Security:** auth is off by default, keys travel in a header with no TLS termination here, and
  nothing is rate limited. The API is not hosted anywhere.
- **Nothing is pushed.** The repository exists only locally so far.

## Tables marked `verify: true`

| Table (`data/`) | Marked | Why |
| --------------- | ------ | --- |
| `durmuhurta.yaml` | table, and all 7 weekday rows | Recalled from memory; traditions disagree, especially Tuesday, Thursday, Saturday and night muhurtas. The Tuesday night muhurta (8) is a guess. |
| `varjyam.yaml` | table | The 27 start ghatikas were recalled from the usual Muhurta Chintamani list and not checked. |
| `gowri.yaml` | table, and all 7 weekday rows | Recalled from memory. Day rows follow "cycle starts at the weekday's own name"; night rows assume the cycle starts four names later, which is unconfirmed. |
| `functional.yaml` | table | Derived from sign lordships; the rank precedence is a project convention (see above). |
| `hora_generic.yaml` | table | Placeholder ranking with no source. |

Not marked, and taken from the brief: `horas.yaml`, `kalams.yaml`, and the tara and chandra
qualities in `tarabala.yaml` and `chandrabala.yaml`. Also not marked: `names.yaml` and
`friendship.yaml` (standard lists, still worth a check).

## Release contents

`s1-*` feature tags: scaffold, astro-core, hora-engine, personal-scoring, rasi-scoring,
http-api. See `CHANGELOG.md` for the per-feature summary.
