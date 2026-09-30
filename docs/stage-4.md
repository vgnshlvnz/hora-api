# Stage 4: table accuracy follow-up

Version 0.4.0. Builds on stage 3 (`docs/stage-3.md`). Decisions are in `docs/stage-4-decisions.md`
and the table checks are logged in `docs/table-verification.md`.

## What shipped

| Feature | Tag | What it is |
| ------- | --- | ---------- |
| gowri-verification | `s4-gowri-verification` | `gowri.yaml` replaced with Drik Panchang's day and night sequences (Kuala Lumpur, 2026-11-01 to 2026-11-07); Uthi is good, not bad |

## Table state at close

| Table | State |
| ----- | ----- |
| `durmuhurta` | all 7 weekdays match Drik Panchang; not reported as unverified |
| `varjyam` | 26 of 27 nakshatras match Drik; **Mula** stays `verify: true` (a second window at 56 ghatikas is not modelled) |
| `gowri` | Sunday to Friday match Drik; **Saturday night** stays `verify: true` (Drik printed Soram twice; the 8th segment, Rogam, is inferred) |
| `functional` | not checked: needs a sourced text |
| `hora_generic` | conventional benefic/variable/malefic grouping, no primary text, `verify: true` |

The recalled Gowri table was wrong in 11 of 14 sequences (it was built as a cycle; Drik's is not),
and Uthi's nature was inverted, which changed good/bad labels in the API and the day card.

## Known limitations

- **Unverified tables in use:** `varjyam` (Mula only), `gowri` (Saturday night only), `functional`,
  `hora_generic`. Responses still list them in `unverified_tables`.
- **Checks cover one place** (Kuala Lumpur) **and one tradition** (Drik Panchang).
- **Mula varjyam** needs a second window in the model, or a decision to ignore it.
- **Deployment files are still unproven on a real host**; no TLS; chandrabala paksha values are
  placeholders; no pratyantar dasha.
- **Git tags are local**: pushing tags from the cloud session failed, so publishing them is manual.

## Run it

```
make install && make hooks
make check
make run
```
