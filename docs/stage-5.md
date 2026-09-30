# Stage 5: varjyam model

Version 0.5.0. Builds on stage 4 (`docs/stage-4.md`). Decisions are in `docs/stage-5-decisions.md`
and the table checks are logged in `docs/table-verification.md`.

## What shipped

| Feature | Tag | What it is |
| ------- | --- | ---------- |
| mula-varjyam-window | `s5-mula-varjyam-window` | a nakshatra can have several varjyam windows (`start_ghati` may be a list); Mula has two, at 20 and 56 ghatikas, as Drik Panchang lists |

## Table state at close

| Table | State |
| ----- | ----- |
| `durmuhurta` | all 7 weekdays match Drik Panchang; not reported as unverified |
| `varjyam` | 26 of 27 nakshatras match Drik; **Mula** has two windows, each seen once on Drik, and stays `verify: true` |
| `gowri` | Sunday to Friday match Drik; **Saturday night** stays `verify: true` (Drik printed Soram twice; the 8th segment, Rogam, is inferred) |
| `functional` | not checked: needs a sourced text |
| `hora_generic` | conventional benefic/variable/malefic grouping, no primary text, `verify: true` |

## Known limitations

- **Unverified tables in use:** `varjyam` (Mula only), `gowri` (Saturday night only), `functional`,
  `hora_generic`. Responses still list them in `unverified_tables`.
- **Mula's windows rest on one Mula day** (2026-11-12 and 2026-11-13, Kuala Lumpur); a second
  Mula day would confirm them. Whether other nakshatras have a second window is unchecked.
- **Checks cover one place** (Kuala Lumpur) **and one tradition** (Drik Panchang).
- **Deployment files are still unproven on a real host**; no TLS; chandrabala paksha values are
  placeholders; no pratyantar dasha.
- **Git tags** made in the cloud session cannot be pushed from it (403); publish them from a clone.

## Run it

```
make install && make hooks
make check
make run
```
