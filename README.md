# hora-api

A Python HTTP API that answers "which horas and time windows are favourable for a given person,
date and place". It computes a panchangam-style day (sunrise, sunset, nakshatra, rasi, tithi
transitions), divides it into horas, removes inauspicious windows, and scores what's left against
a person's natal data.

See `CLAUDE.md` for the domain rules and git workflow, and `ROADMAP.md` for progress.

## Make targets

| Target         | What it does                                              |
| -------------- | --------------------------------------------------------- |
| `make install` | Install dependencies with `uv sync`                       |
| `make hooks`   | Enable `.githooks` and the commit template (once per clone) |
| `make lint`    | `ruff check` and `ruff format --check`                    |
| `make fmt`     | Apply `ruff format` and `ruff check --fix`                |
| `make type`    | `mypy --strict`                                           |
| `make test`    | `pytest`                                                  |
| `make cov`     | `pytest` with coverage report                             |
| `make check`   | `lint` + `type` + `test`                                  |
| `make run`     | Serve the API with uvicorn on http://127.0.0.1:8000        |

## API

`make run`, then see `http://127.0.0.1:8000/v1/docs`. OpenAPI is at `/v1/openapi.json`.

| Endpoint | Purpose |
| -------- | ------- |
| `GET /v1/day` | Sun events, transitions, horas, blocked windows, Gowri layer |
| `GET /v1/horas/personal?profile_id=` | Scored horas and top windows for a stored profile |
| `POST /v1/horas/personal` | Same, with an inline `Profile` body |
| `GET /v1/horas/rasi` | 12 x 24 rasi matrix |
| `GET /v1/cards/day` | Day summary as a client-neutral chat card |
| `GET /v1/cards/rasi` | Rasi overview as a client-neutral chat card |
| `GET /v1/cards/personal?profile_id=` | Personal windows chat card for a stored profile |
| `GET /v1/profiles` | Profile ids and display names only |
| `GET /healthz`, `GET /readyz` | Liveness and readiness |

Common query parameters: `date`, `lat`, `lon`, `tz`, `convention` (`tamil` default, or
`classical`) and `ayanamsa` (`lahiri` default, or `kp`). Errors are RFC 9457 `problem+json`.

Configuration (environment): `PROFILES_PATH` (default `~/.config/hora-api/profiles.yaml`, outside
the repo), `API_KEYS` (comma-separated; empty turns auth off, otherwise send `X-API-Key`),
`DEFAULT_LAT`, `DEFAULT_LON`, `DEFAULT_TZ` (default Petaling Jaya), `CACHE_SIZE`,
`MIN_WINDOW_MINUTES`, `DATA_DIR`. Scoring weights: `HORA_SCORING_*`.

### Chat cards

`/v1/cards/*` take the same query parameters and return a card: `kind`, `title`, `subtitle`,
ordered `sections` (each with a stable `id`, a `title` and label/value `rows`, each row with a
`tone` of `good`, `bad` or `neutral`), and a `footer` naming any unverified tables in use. Times
are ready-to-show `HH:MM` strings in the request's timezone, with `+1` after local midnight.
Day card sections: `sun`, `moon`, `avoid`, `nalla_neram`, `horas`. Rasi card sections:
`chandrashtama`, `best`, `all`. Personal card sections (stored `profile_id` only): `top` (best
windows), `blocked` (why fully blocked horas were removed) and `tara_chandra`.

## MCP server

`mcp-server/` holds `hora-mcp`, an MCP server (streamable HTTP) that wraps this API with tools
for the day card, the rasi card and personal horas. It is a separate uv project; see
`mcp-server/README.md`.

## Self-hosting

`deploy/` holds a Docker Compose setup and systemd units for running the API and the MCP server
on a home server (LAN, plain HTTP, keys required), and `scripts/smoke.sh` checks a running
deployment. A `watcher` sidecar restarts unhealthy containers (capped, with a status file). See
`docs/self-hosting.md`.

## Chandrabala and paksha

Chandrabala houses 2, 5 and 9 are conditional: their value depends on paksha (shukla or krishna,
from the tithi at the start of the hora). Set `HORA_SCORING_CHANDRA_CONDITIONAL_SHUKLA_VALUE`
(default 1.0) and `HORA_SCORING_CHANDRA_CONDITIONAL_KRISHNA_VALUE` (default 0.5), or turn the
split off with `HORA_SCORING_CHANDRA_PAKSHA=false` to use the single
`HORA_SCORING_CHANDRA_CONDITIONAL_VALUE`. Scored horas and the rasi matrix use the paksha at the
start of the hora; the personal card splits its chandrabala rows at the full and new moon.

## Dasha

Scoring can include a dasha component. A profile supplies it in one of two ways: explicit
`dasha` periods, or an optional `birth_datetime` (timezone-aware) from which Vimshottari dasha and
bhukti periods are computed using the Moon's longitude then, in the request's ayanamsa. Year length
is `HORA_SCORING_DASHA_YEAR_DAYS` (default 365.25). `/v1/horas/personal` lists the periods that
overlap the day in `dasha`. The birth time is never returned.

## Keys and tiers

By default the API needs no key. Set `API_KEYS` (owner keys) and/or a keys file (`KEYS_PATH`,
managed with `hora-keys`) and every `/v1` request needs `X-API-Key`. A key file entry has a tier:
`free` keys may use the day endpoints only; `paid` keys may use everything, limited to the stored
profiles their entry lists. Free keys get a 403 problem on paid endpoints. See
`docs/self-hosting.md`.
