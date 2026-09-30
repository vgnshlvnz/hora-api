# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- scaffold: repo layout, tooling, git hooks and workflow scripts.
- astro-core: `hora_api.core.astro` with sun events, moon state, tithi and nakshatra/rasi/tithi transitions (Lahiri and KP).
- hora-engine: `hora_api.core.day` (horas in tamil and classical conventions, kalams, durmuhurta, varjyam, gowri, blocked windows, clean parts) and the `data/*.yaml` tables with their loader; durmuhurta, varjyam and gowri are `verify: true`.
- personal-scoring: `hora_api.scoring.personal` (Profile, derive_profile, tarabala, chandrabala, hora-lord rank, dasha match, per-hora scores with tara/chandra change info), `ScoringSettings`, and the names, tarabala, chandrabala, functional and friendship tables; `functional` is `verify: true`. Also `core.astro.ascendant`.
