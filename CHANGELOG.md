# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.5.0] - Stage 5

### Added

- mula-varjyam-window: a nakshatra can have more than one varjyam window (`start_ghati` may be a list in `varjyam.yaml`; `VarjyamTable.start_ghatis`), and Mula has two, at 20 and 56 ghatikas, as Drik Panchang lists (Kuala Lumpur, 2026-11-13). Hora overlapping Mula's second window are now blocked. Mula stays `verify: true` (each window seen once).

## [0.4.0] - Stage 4

### Fixed

- gowri-verification: `gowri.yaml` was a recalled cycle and mostly wrong; 11 of 14 day and night sequences now follow Drik Panchang (Kuala Lumpur, 2026-11-01 to 2026-11-07), and Uthi is good, not bad (this changes the nature of Uthi segments in the API and the day card). Six weekdays are `verify: false`; Saturday stays `verify: true` (Drik's 8th night segment is ambiguous, Rogam is inferred). See `docs/table-verification.md`.

## [0.3.0] - Stage 3

### Fixed

- table-verification: checked `durmuhurta.yaml` and `varjyam.yaml` against Drik Panchang (Kuala Lumpur, 2026-11-01 to 2026-11-28 and 2026-10-30). Varjyam: Ardra 11 -> 21 and Hasta 22 -> 21; 26 of 27 rows are now `verify: false`, Mula stays open (Drik lists a second window). Durmuhurta: Tuesday night 8 -> 7, Thursday day 7 -> 6 and 12, Saturday day 1 -> 1 and 2; the table is fully checked and no longer reported as unverified. Per-nakshatra `verify` flags are reported as `varjyam:<name>`. Gowri and functional remain unverified. See `docs/table-verification.md`.

### Added

- hora-generic-source: `hora_generic.yaml` now uses the conventional benefic (Jupiter, Venus 1.0), variable (Moon, Mercury 0.5) and malefic (Sun, Mars, Saturn 0.0) grouping instead of the five-step placeholder (Sun moves 0.25 to 0.0, Moon and Mercury 0.75 to 0.5). It has no primary text, so it stays `verify: true` and the rasi hora term stays off by default.
- api-tiers: per-subscriber API keys in a keys file (hashed, `hora-keys` CLI, reloaded on change) with `free` and `paid` tiers, 403 `tier-required` on paid endpoints, per-key stored-profile scopes, owner keys via `API_KEYS`, key ids in logs, fail-closed keys file; MCP passthrough mode forwarding each caller's own key; deploy files and smoke test updated.
- vimshottari-dasha: `core.dasha` computes Vimshottari maha and antar periods from the Moon's longitude at birth; profiles take an optional `birth_datetime` (never returned), scoring uses computed periods when no explicit `dasha` is given, and `/v1/horas/personal` lists the periods overlapping the day; `data/vimshottari.yaml`, `dasha_year_days` setting.
- paksha-chandrabala: chandrabala houses 2, 5 and 9 take a value per paksha (`chandra_conditional_shukla_value` 1.0, `chandra_conditional_krishna_value` 0.5), judged at the start of the hora, on by default (`chandra_paksha`); `core.astro.paksha`; the personal card splits chandrabala rows at the full and new moon.
- docker-autorestart: a `watcher` sidecar in `deploy/` (`watcher.py`, compose service and Dockerfile target) that restarts unhealthy labelled containers, capped at 3 per 30 minutes, then gives up and writes a status file; `scripts/smoke.sh` can check that file.
- personal-card: `GET /v1/cards/personal?profile_id=` (best windows, why horas are blocked, tara and chandra over the day) and the `hora_personal_card` MCP tool.

## [0.2.0] - Stage 2

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
