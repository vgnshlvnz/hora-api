# Stage 3: accuracy, personal card and hosting hardening

Version 0.3.0. Builds on stage 2 (`docs/stage-2.md`). Decisions are in `docs/stage-3-decisions.md`
and the table checks are logged in `docs/table-verification.md`.

## What shipped

| Feature | Tag | What it is |
| ------- | --- | ---------- |
| table-verification | `s3-table-verification` | `durmuhurta` and `varjyam` checked against Drik Panchang (Kuala Lumpur, 28 days from 2026-11-01); 5 wrong values fixed |
| hora-generic-source | `s3-hora-generic-source` | `hora_generic` is now a benefic/variable/malefic grouping (1.0 / 0.5 / 0.0); still unsourced |
| vimshottari-dasha | `s3-vimshottari-dasha` | maha and antar periods computed from the Moon at birth |
| paksha-chandrabala | `s3-paksha-chandrabala` | per-paksha values for chandrabala houses 2, 5 and 9 |
| personal-card | `s3-personal-card` | `GET /v1/cards/personal` and the `hora_personal_card` MCP tool |
| docker-autorestart | `s3-docker-autorestart` | `watcher` sidecar restarting unhealthy containers, capped |
| api-tiers | `s3-api-tiers` | per-subscriber keys, `free` and `paid` tiers, profile scopes, revocation |

Skipped: `tls-proxy` (the API stays on the LAN).

## Table state at close

| Table | State |
| ----- | ----- |
| `durmuhurta` | all 7 weekdays match Drik Panchang; no longer reported as unverified |
| `varjyam` | 26 of 27 nakshatras match Drik; **Mula** stays `verify: true` (Drik lists a second window at 56 ghatikas that the table cannot hold) |
| `gowri` | **not checked**: Drik's day pages do not include Gowri Panchangam |
| `functional` | **not checked**: needs a sourced text |
| `hora_generic` | conventional grouping, no primary text, `verify: true` |

Corrections made: Ardra varjyam 11 to 21, Hasta varjyam 22 to 21, Tuesday durmuhurta night 8 to 7,
Thursday day 7 to 6 and 12, Saturday day 1 to 1 and 2. Checks are against one place (Kuala Lumpur)
and one tradition (Drik Panchang); the YAML comments carry the dates.

## Known limitations

- **Unverified tables in use:** `varjyam` (Mula only), `gowri`, `functional`, `hora_generic`.
  Cards and API responses still list them in `unverified_tables`.
- **Mula varjyam** needs a second window in the model, or a decision to ignore it.
- **Deployment files are still unproven on a real host** (carried over from stage 2); no TLS.
- **Chandrabala paksha defaults** (1.0 shukla, 0.5 krishna) are placeholders, not sourced.
- **Dasha:** no pratyantar level and no other dasha systems.
- **Git tags** are local: pushing tags from the cloud session failed (the git proxy hung up), so
  publishing them is a manual step.
- No golden personal-card snapshot was saved at close (it would need the real profile).

## Run it

```
make install && make hooks
make check
make run
```
