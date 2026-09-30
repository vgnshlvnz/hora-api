# Stage 6: decisions

Stage 5 closed with these items open (`docs/stage-5.md`). Stage 6 takes three of them.

## Decided

| Area | In stage 6 | Not in stage 6 |
| ---- | ---------- | -------------- |
| Sources | `functional-source`: a cited functional-nature table per lagna; `chandrabala-paksha-source`: cited values for houses 2, 5 and 9 by paksha | Validating the deployment files on a real host (needs a host), TLS, pratyantar dasha |
| Second checks | `second-check`: Drik Panchang for a second lunar month: a second Mula day, other nakshatras' second varjyam windows, Saturday night Gowri, and the weekday durmuhurta and Gowri rows again | A second place or another tradition, unless one is named |

## What each feature needs from the project owner

- **functional-source** and **chandrabala-paksha-source** need a source text (book, edition, page or
  table) named by the project owner. Without one, a row stays `verify: true` and the work is
  limited to recording what was and was not found. Claude does not supply values from memory.
- **second-check** needs Drik Panchang pages saved from the owner's machine (the cloud session
  cannot fetch them): one day page per day for the month, and the Gowri page for any day that
  needs it, with the same extract commands used in stage 3 and 4 (`docs/table-verification.md`).

## Still open

- **Which month and place** for `second-check`: a second lunar month for Kuala Lumpur is assumed;
  say if another place is wanted.
- **Which tradition** to follow for `chandrabala-paksha-source` where sources disagree (the same
  question as for durmuhurta: Drik Panchang was the reference there).
- **Carried over:** the deployment files are unproven on a real host; no TLS; no pratyantar dasha.
