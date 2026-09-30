# Stage 5: decisions

Stage 4 closed with the Mula varjyam question open (`docs/stage-4.md`). Stage 5 opens to settle it.

## Decided

| Area | In stage 5 | Not in stage 5 |
| ---- | ---------- | -------------- |
| Varjyam model | `mula-varjyam-window`: a nakshatra may have more than one `start_ghati`; Mula gets 20 and 56, both seen on Drik Panchang (Kuala Lumpur, 2026-11-13: 01:48-03:36 and 17:59-19:47) | Other nakshatras with a second window (none appeared in the 28 days checked), other places, other traditions |

## Finding that opened the stage

Checking `varjyam.yaml` against Drik (`docs/table-verification.md`), every nakshatra had one
window of 4 ghatikas at its table value, except Mula, where Drik listed two in the same
nakshatra: 20 ghatikas in (the table value) and 56 ghatikas in, ending with the nakshatra. The
table holds one `start_ghati` per nakshatra, so the second window is missing and any hora that
overlaps it is not blocked.

## Still open

- **Only one Mula occurrence was seen** (2026-11-12 and 2026-11-13). The second window rests on
  that one sample, so Mula stays `verify: true` until a second Mula day matches.
- **Do other nakshatras have a second window?** None showed one in 28 days, but a second window
  near a nakshatra's end can be clipped by the Drik day boundary. A second check on a later
  lunar month would settle it.
- **Carried from earlier stages:** Saturday night Gowri (8th segment inferred), `functional` has
  no sourced text, `hora_generic` has no primary text, the deployment files are unproven on a
  real host, the chandrabala paksha values are placeholders.
