#!/usr/bin/env bash
# Usage: scripts/finish-feature.sh <stage> <feature> [--dry-run]
# Runs make check in the feature worktree, refuses if the ROADMAP tick or CHANGELOG line is
# missing, then rebases if needed, merges into stage/N, tags, and removes worktree and branch.
# Every git command is printed before it runs. --dry-run prints them without running anything
# (validation still runs; make check is skipped).
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/_lib.sh
source "$here/_lib.sh"

DRY_RUN=0; args=()
for a in "$@"; do [[ $a == --dry-run ]] && DRY_RUN=1 || args+=("$a"); done
((${#args[@]} == 2)) || die "usage: scripts/finish-feature.sh <stage> <feature> [--dry-run]"
stage=${args[0]}; feature=${args[1]}
[[ $stage =~ ^[0-9]+$ ]] || die "stage must be a number, got '$stage'"
[[ $feature =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "feature must be lowercase kebab-case, got '$feature'"

cd "$(main_worktree)"
branch="s$stage/$feature"
wt="../hora-api-$feature"
tag="s$stage-$feature"

# --- Preflight (read-only) ---
git rev-parse --verify -q "stage/$stage" >/dev/null || die "branch stage/$stage does not exist"
git rev-parse --verify -q "$branch" >/dev/null || die "branch $branch does not exist"
[[ -d $wt ]] || die "worktree $wt does not exist"
[[ $(git -C "$wt" branch --show-current) == "$branch" ]] || die "$wt is not on branch $branch"
[[ -z $(git -C "$wt" status --porcelain) ]] || die "$wt has uncommitted changes"
[[ -z $(git status --porcelain) ]] || die "main worktree has uncommitted changes"
git rev-parse --verify -q "refs/tags/$tag" >/dev/null && die "tag $tag already exists"

entry=$(git -C "$wt" show "HEAD:ROADMAP.md" | stage_section "$stage" | feature_entry "$feature")
[[ -n $entry ]] || die "'$feature' is not listed under stage $stage in ROADMAP.md"
[[ ${entry%%|*} == x ]] || die "ROADMAP.md: '$feature' is not ticked ('- [x] $feature:') on $branch"
summary=${entry#*|}

git -C "$wt" show "HEAD:CHANGELOG.md" | unreleased_section | grep -Fq -- "$feature" \
  || die "CHANGELOG.md: no line mentioning '$feature' under [Unreleased] on $branch"

# --- Rebase onto stage/N if it moved ---
if ! git merge-base --is-ancestor "stage/$stage" "$branch"; then
  echo "stage/$stage moved; rebasing $branch"
  run git -C "$wt" rebase "stage/$stage"
fi

# --- Gate ---
echo "+ make -C $wt check"
if [[ $DRY_RUN == 1 ]]; then echo "  (skipped in --dry-run)"; else make -C "$wt" check; fi

# --- Merge, tag, clean up ---
run git switch "stage/$stage"
run git merge --no-ff "$branch" -m "merge(s$stage): $feature" \
  -m "Stage: $stage"$'\n'"Feature: $feature"
run git tag -a "$tag" -m "${summary:-$feature}"
run git worktree remove "$wt"
run git branch -d "$branch"
