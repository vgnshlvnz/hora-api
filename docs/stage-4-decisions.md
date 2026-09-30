# Stage 4: decisions

Stage 3 closed with tables still unverified (`docs/stage-3.md`). Stage 4 opens with one item, found
while checking `gowri` against Drik Panchang after the close.

## Decided

| Area | In stage 4 | Not in stage 4 |
| ---- | ---------- | -------------- |
| Accuracy and data | `gowri-verification`: take the day and night Nalla Neram sequences for all 7 weekdays from Drik Panchang (Kuala Lumpur, 2026-11-01 to 2026-11-07) and fix the nature of Uthi (Drik: good) | |

## Finding that opened the stage

The `gowri.yaml` rows were recalled as a cycle starting at each weekday's own name. Against Drik,
only Sunday (day and night) and Wednesday (day) were right; 11 of 14 sequences differ, and Drik's
table is not a cycle. Drik also lists Uthi as good; the table had it bad. Drik's page for
Saturday night prints Soram twice and no Rogam, so that row cannot be fully verified from it.

## Still open

- **Saturday night Gowri:** Drik's 8th segment (printed Soram) looks like a page error. Check
  against a printed panchangam or another Drik date before clearing `verify`.
- **Carried from stage 3:** Mula has a second varjyam window at 56 ghatikas that the table
  cannot express; `functional` has no sourced text; `hora_generic` has no primary text; the
  deployment files are unproven on a real host; the chandrabala paksha values are placeholders.
