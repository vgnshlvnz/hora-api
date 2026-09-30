#!/usr/bin/env bash
# Usage: scripts/new-feature.sh <stage> <feature> [--dry-run]
# Verifies the feature is listed under the current stage in ROADMAP.md (on stage/N), creates
# the worktree and branch, and makes the "in progress" commit.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/_lib.sh
source "$here/_lib.sh"

DRY_RUN=0; args=()
for a in "$@"; do [[ $a == --dry-run ]] && DRY_RUN=1 || args+=("$a"); done
((${#args[@]} == 2)) || die "usage: scripts/new-feature.sh <stage> <feature> [--dry-run]"
stage=${args[0]}; feature=${args[1]}
[[ $stage =~ ^[0-9]+$ ]] || die "stage must be a number, got '$stage'"
[[ $feature =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "feature must be lowercase kebab-case, got '$feature'"

cd "$(main_worktree)"
branch="s$stage/$feature"
wt="../hora-api-$feature"

git rev-parse --verify -q "stage/$stage" >/dev/null || die "branch stage/$stage does not exist"
roadmap=$(git show "stage/$stage:ROADMAP.md") || die "ROADMAP.md not found on stage/$stage"
grep -Eq "^## Stage $stage: .*\(current\)" <<<"$roadmap" \
  || die "stage $stage is not the current stage in ROADMAP.md"
entry=$(stage_section "$stage" <<<"$roadmap" | feature_entry "$feature")
[[ -n $entry ]] || die "'$feature' is not listed under stage $stage in ROADMAP.md on stage/$stage.
Add it there first, in a commit on stage/$stage."
[[ ${entry%%|*} == " " ]] || die "'$feature' is already marked '[${entry%%|*}]' in ROADMAP.md"
git rev-parse --verify -q "$branch" >/dev/null && die "branch $branch already exists"
[[ -e $wt ]] && die "$wt already exists"

run git worktree add "$wt" -b "$branch" "stage/$stage"
run sed -i.bak -E "s/^- \[ \] ($feature):/- [~] \1:/" "$wt/ROADMAP.md"
run rm -f "$wt/ROADMAP.md.bak"
run git -C "$wt" add ROADMAP.md
run git -C "$wt" commit -m "docs($feature): mark $feature in progress" \
  --trailer "Stage: $stage" --trailer "Feature: $feature"

echo
echo "Next: cd $wt && make install"
