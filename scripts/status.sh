#!/usr/bin/env bash
# Usage: scripts/status.sh
# Current stage, features done / in progress / planned (ROADMAP.md on the newest stage/N branch,
# cross-checked against s<N>-* tags, s<N>/* branches and worktrees), active worktrees, and
# commits on stage/N since the last feature tag. Exit status 1 if any mismatch is flagged.
# "scaffold" is an implicit stage-1 feature: done once tag s1-scaffold exists.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/_lib.sh
source "$here/_lib.sh"
cd "$(main_worktree)"

mismatches=()
flag() { mismatches+=("$*"); }

# ROADMAP source: newest stage/N branch (where features land), else the working copy.
newest=$(git for-each-ref --format='%(refname:short)' 'refs/heads/stage/*' | sort -t/ -k2 -n | tail -n1)
if [[ -n $newest ]]; then roadmap=$(git show "$newest:ROADMAP.md"); else roadmap=$(<ROADMAP.md); fi

cur_line=$(grep -E '^## Stage [0-9]+: .*\(current\)' <<<"$roadmap" | head -n1 || true)
if [[ -z $cur_line ]]; then
  cur_line=$(grep -E '^## Stage [0-9]+: .*\(complete\)' <<<"$roadmap" | tail -n1 || true)
fi
[[ -n $cur_line ]] || die "no current or complete stage found in ROADMAP.md"
stage=$(sed -E 's/^## Stage ([0-9]+):.*/\1/' <<<"$cur_line")
complete=0; [[ $cur_line == *"(complete)"* ]] && complete=1
sbranch="stage/$stage"
git rev-parse --verify -q "$sbranch" >/dev/null || die "branch $sbranch does not exist"

echo "Current stage: ${cur_line#\#\# }"
if ((complete)); then
  echo "Stage $stage complete."
  git rev-parse --verify -q "refs/tags/stage-$stage" >/dev/null \
    || flag "ROADMAP says stage $stage is complete but tag stage-$stage is missing"
elif git rev-parse --verify -q "refs/tags/stage-$stage" >/dev/null; then
  flag "tag stage-$stage exists but ROADMAP does not mark stage $stage complete"
fi

# --- Features ---
declare -A rstate rdesc
order=()
while IFS='|' read -r name st desc; do
  order+=("$name"); rstate[$name]=$st; rdesc[$name]=$desc
done < <(stage_section "$stage" <<<"$roadmap" \
  | sed -nE 's/^- \[(.)\] ([a-z0-9-]+): ?(.*)$/\2|\1|\3/p')

worktree_branches=$(git worktree list --porcelain | sed -n 's|^branch refs/heads/||p')
has_tag()    { git rev-parse --verify -q "refs/tags/$1" >/dev/null; }
has_branch() { git rev-parse --verify -q "refs/heads/$1" >/dev/null; }

done_list=(); prog_list=(); plan_list=()

# Implicit scaffold feature (stage 1 only).
if [[ $stage == 1 && -z ${rstate[scaffold]:-} ]]; then
  if has_tag s1-scaffold; then
    git merge-base --is-ancestor s1-scaffold "$sbranch" \
      || flag "tag s1-scaffold is not reachable from $sbranch"
    done_list+=("scaffold (tag s1-scaffold)")
  else
    prog_list+=("scaffold (no tag s1-scaffold yet)")
  fi
fi

for f in "${order[@]}"; do
  st=${rstate[$f]}; tag="s$stage-$f"; br="s$stage/$f"
  tagged=0; has_tag "$tag" && tagged=1
  branched=0; has_branch "$br" && branched=1
  wtree=0; grep -qx "$br" <<<"$worktree_branches" && wtree=1

  if [[ $st == x ]]; then
    done_list+=("$f")
    ((tagged)) || flag "$f: ticked in ROADMAP but no $tag tag"
    ((tagged)) && ! git merge-base --is-ancestor "$tag" "$sbranch" \
      && flag "$f: tag $tag is not reachable from $sbranch (not merged?)"
    ((branched)) && flag "$f: done, but branch $br still exists"
    ((wtree)) && flag "$f: done, but a worktree for $br still exists"
  else
    ((tagged)) && flag "$f: tag $tag exists but ROADMAP on $sbranch is not ticked"
    [[ $st == '~' ]] && flag "$f: '[~]' on $sbranch; in-progress marks belong on the feature branch"
    if ((branched)); then
      prog_list+=("$f ($br)")
      ((wtree)) || flag "$f: branch $br has no worktree"
      git show "$br:ROADMAP.md" 2>/dev/null | stage_section "$stage" | feature_entry "$f" \
        | grep -q '^ |' && flag "$f: branch $br exists but ROADMAP on it is still '[ ]'"
    else
      plan_list+=("$f")
      ((wtree)) && flag "$f: worktree for $br exists without the branch"
    fi
  fi
done

# Stray tags and branches not in ROADMAP.
while IFS= read -r t; do
  n=${t#"s$stage-"}
  [[ $n == scaffold && $stage == 1 ]] && continue
  [[ -n ${rstate[$n]:-} ]] || flag "tag $t has no matching feature in ROADMAP.md"
done < <(git tag -l "s$stage-*")
while IFS= read -r b; do
  [[ -n $b ]] || continue
  n=${b#*/}
  [[ -n ${rstate[$n]:-} ]] || flag "branch $b has no matching feature in ROADMAP.md"
done < <(git branch --list "s$stage/*" --format='%(refname:short)')

show() {
  local title=$1; shift
  printf '\n%s (%d)\n' "$title" "$#"
  if (($#)); then printf '  - %s\n' "$@"; else echo "  none"; fi
}
show "Done" "${done_list[@]}"
show "In progress" "${prog_list[@]}"
show "Planned" "${plan_list[@]}"

printf '\nActive worktrees\n'
git worktree list | sed 's/^/  /'

printf '\nCommits on %s since last feature tag\n' "$sbranch"
last=$(git describe --tags --abbrev=0 --match "s$stage-*" "$sbranch" 2>/dev/null || true)
if [[ -n $last ]]; then
  echo "  (since $last)"; range="$last..$sbranch"
else
  echo "  (no feature tag yet; all commits)"; range=$sbranch
fi
if [[ -n $(git rev-list "$range" | head -n1) ]]; then
  git log --oneline "$range" | sed 's/^/  /'
else
  echo "  none"
fi

if ((${#mismatches[@]})); then
  printf '\nMISMATCHES\n'
  printf '  ! %s\n' "${mismatches[@]}"
  exit 1
fi
printf '\nNo mismatches.\n'
