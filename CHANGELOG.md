# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- self-hosting: `deploy/` (Dockerfile with `api` and `mcp` targets, Docker Compose, systemd units and a readiness timer, env examples, container health probe), `scripts/smoke.sh`, and the `docs/self-hosting.md` runbook including profiles backup and restore.
- mcp-server: `mcp-server/` (hora-mcp), an MCP server over streamable HTTP wrapping the API with `hora_day_card`, `hora_rasi_card` and `hora_personal_horas`; optional bearer token; root `make check` now also gates it.
- chat-cards: client-neutral chat cards from the API, `GET /v1/cards/day` and `GET /v1/cards/rasi` (sections with stable ids, tone per row, times in the request timezone).

## [0.1.0] - Stage 1

### Added

- scaffold: repo layout, tooling, git hooks and workflow scripts.
- astro-core: `hora_api.core.astro` with sun events, moon state, tithi and nakshatra/rasi/tithi transitions (Lahiri and KP).
- hora-engine: `hora_api.core.day` (horas in tamil and classical conventions, kalams, durmuhurta, varjyam, gowri, blocked windows, clean parts) and the `data/*.yaml` tables with their loader; durmuhurta, varjyam and gowri are `verify: true`.
- personal-scoring: `hora_api.scoring.personal` (Profile, derive_profile, tarabala, chandrabala, hora-lord rank, dasha match, per-hora scores with tara/chandra change info), `ScoringSettings`, and the names, tarabala, chandrabala, functional and friendship tables; `functional` is `verify: true`. Also `core.astro.ascendant`.
- rasi-scoring: `hora_api.scoring.rasi` 12 x 24 chandrabala matrix with universal hard filters, per-rasi day percentage, and an optional generic hora-lord term (off by default; `hora_generic` table is `verify: true`).
- http-api: FastAPI `/v1` endpoints (`day`, `horas/personal` GET and POST, `horas/rasi`, `profiles`), `/healthz`, `/readyz`, problem+json errors, optional `X-API-Key` auth, LRU day cache and an external profiles file.
