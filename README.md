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
| `GET /v1/profiles` | Profile ids and display names only |
| `GET /healthz`, `GET /readyz` | Liveness and readiness |

Common query parameters: `date`, `lat`, `lon`, `tz`, `convention` (`tamil` default, or
`classical`) and `ayanamsa` (`lahiri` default, or `kp`). Errors are RFC 9457 `problem+json`.

Configuration (environment): `PROFILES_PATH` (default `~/.config/hora-api/profiles.yaml`, outside
the repo), `API_KEYS` (comma-separated; empty turns auth off, otherwise send `X-API-Key`),
`DEFAULT_LAT`, `DEFAULT_LON`, `DEFAULT_TZ` (default Petaling Jaya), `CACHE_SIZE`,
`MIN_WINDOW_MINUTES`, `DATA_DIR`. Scoring weights: `HORA_SCORING_*`.
