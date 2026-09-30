# Shared helpers for scripts/*.sh (sourced, not executed).

die() { echo "error: $*" >&2; exit 1; }

# Path of the main worktree (first entry of `git worktree list`).
main_worktree() { git worktree list --porcelain | sed -n '1s/^worktree //p'; }

# Quote an argument for display only when it needs it.
quote() {
  if [[ $1 =~ ^[A-Za-z0-9_@%+=:,./~-]+$ ]]; then printf '%s' "$1"
  else printf "'%s'" "${1//\'/\'\\\'\'}"; fi
}

# Print a command, then run it unless DRY_RUN=1.
run() {
  local out=+ a
  for a in "$@"; do out+=" $(quote "$a")"; done
  echo "$out"
  [[ ${DRY_RUN:-0} == 1 ]] || "$@"
}

# Lines of the "## Stage N: ..." section of ROADMAP.md text on stdin.
stage_section() {
  awk -v n="$1" '
    /^## / { on = ($0 ~ "^## Stage " n ":") }
    on
  '
}

# "type|description" for a feature line in a section on stdin, e.g. " |sunrise/sunset ...".
feature_entry() {
  sed -nE "s/^- \[(.)\] $1: ?(.*)$/\1|\2/p" | head -n1
}

# Lines under "## [Unreleased]" in CHANGELOG text on stdin.
unreleased_section() {
  awk '/^## /{ on = ($0 ~ /^## \[Unreleased\]/) } on'
}
