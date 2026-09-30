# CLAUDE.md — hora-api

Standing brief for every session in this repo. Read it first. ROADMAP.md says what is in the
current stage; this file says how to work.

## Purpose

A Python HTTP API that answers "which horas and time windows are favourable for a given person,
date and place". It computes a panchangam-style day (sunrise, sunset, nakshatra, rasi, tithi
transitions), divides it into horas, removes inauspicious windows, and scores what's left against
a person's natal data.

## Domain rules

The code must follow these.

- Sidereal zodiac. Ayanamsa is configurable (Lahiri default, KP supported).
- Two hora conventions, selectable per request: `tamil` (fixed 60 min from sunrise) and
  `classical` (day length / 12 and night length / 12 separately). Tamil is the default.
- Hora lords follow Chaldean order (Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon); the first
  hora of the day belongs to the weekday lord. The day runs sunrise to next sunrise.
- Hard filters (the window is removed, never merely penalised): Rahu kalam, Yamagandam,
  Gulika kalam, Durmuhurta, Varjyam, and Chandrashtama days for the person.
- Personal score = tarabala + chandrabala + hora-lord rank (from natal lagna) + optional dasha
  match. Weights are configuration, not constants.
- Gowri panchangam (Nalla Neram) is reported as a separate layer, never blended into the score.
- All classical lookup tables live in `data/*.yaml` with a source comment per table. If a table
  value is uncertain, mark it `verify: true` and say so in the summary. Never guess silently.

## Engineering rules

- `src/` layout, package name `hora_api`. `uv` for deps, `ruff`, `mypy --strict`, `pytest`.
- Pure calculation code in `hora_api.core` has no I/O and no FastAPI imports.
- All datetimes are timezone-aware. Internal UTC, output in the request's IANA timezone.
- Birth data is personal. Never commit real birth details; real profiles live outside the repo.
  Tests use a fixture profile `golden` with the same resulting nakshatra/rasi/lagna.

## How to work in this repo

Make targets: `install`, `lint`, `fmt`, `type`, `test`, `cov`, `check` (= lint + type + test),
`run`, `hooks` (sets `core.hooksPath .githooks` and the commit template; run once per clone).

Feature lifecycle (details below): check ROADMAP.md → create worktree/branch → mark "in
progress" → work in small conventional commits → `make check` → rebase, tick ROADMAP, add
CHANGELOG line → merge into `stage/N` with `--no-ff` → tag → remove worktree and branch.

Terminal only: no CI, no issue tracker. `make check` is the gate.

## Git workflow

### Branches

- `main`: completed stages only. Never commit to it directly.
- `stage/N`: integration branch for stage N. Must pass `make check` at every merge.
- `sN/<feature>`: one feature. Created from `stage/N` in its own worktree:

      git worktree add ../hora-api-<feature> -b sN/<feature> stage/N

### Commits

- Conventional commits: `type(scope): summary`. Scope = feature name.
  Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `data` (for YAML table changes).
- Every commit ends with trailers:

      Stage: 1
      Feature: <feature>

  Add them with `git commit --trailer "Stage: 1" --trailer "Feature: <feature>"` or the commit
  template. The commit-msg hook rejects commits without them.
- Commits that change a classical table also add `Source: <text/reference>`.

### Starting a feature

1. Check ROADMAP.md: the feature must be listed under the current stage. If not, add it there
   first in a commit on `stage/N`.
2. Create the worktree and branch (command above).
3. Mark it "in progress" in ROADMAP.md as the first commit on the feature branch
   (`- [ ]` becomes `- [~]`; done is `- [x]`).

`scripts/new-feature.sh <stage> <feature>` does steps 1–3.

### Finishing a feature

1. `make check` passes in the worktree.
2. Rebase onto `stage/N` if it moved: `git rebase stage/N`
3. Tick the feature in ROADMAP.md and add a line under "Unreleased" in CHANGELOG.md.
4. From the main worktree:

       git switch stage/N
       git merge --no-ff sN/<feature> -m "merge(sN): <feature>" \
         -m $'Stage: N\nFeature: <feature>'

   (`git merge` has no `--trailer` flag; the second `-m` becomes the trailer paragraph.)
5. Tag the feature point: `git tag -a sN-<feature> -m "<one-line summary>"`
6. Remove the worktree and branch:

       git worktree remove ../hora-api-<feature> && git branch -d sN/<feature>

`scripts/finish-feature.sh <stage> <feature> [--dry-run]` does steps 1–6.

### Closing a stage

Covered by its own prompt. In short: `stage/N` merges into `main` with `--no-ff`, CHANGELOG
"Unreleased" becomes the stage section, annotated tags `stage-N` and `vX.Y.0` go on the merge.

## Querying progress

Backed by `scripts/status.sh`.

| Question                     | Command                                         |
| ---------------------------- | ----------------------------------------------- |
| Features merged in a stage   | `git log --first-parent --oneline stage/1`      |
| Everything for one feature   | `git log --all --grep "Feature: hora-engine"`   |
| Stage milestones             | `git tag -l "stage-*" -n1`                      |
| Feature tags                 | `git tag -l "s1-*" -n1`                         |
| Open feature branches        | `git branch --list "s*/*"`                      |
| Active worktrees             | `git worktree list`                             |
