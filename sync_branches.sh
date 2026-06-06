#!/usr/bin/env bash
# Sync workflow: merge a source branch into main, then propagate main into
# every OTHER local branch. Branch list is auto-discovered (nothing hardcoded),
# so this stays correct as branches come and go. Idempotent and resumable —
# re-run it any time; already-synced branches just no-op.
#
# Usage:
#   ./sync_branches.sh                  # source = current branch
#   ./sync_branches.sh <source-branch>  # explicit source branch
#   MAIN_BRANCH=trunk ./sync_branches.sh <src>   # override target (default: main)
#
# Behaviour:
#   1. Push <source>, then merge <source> into <main> (fast-forward when
#      possible) and push <main>.
#   2. Merge <main> into every other local branch and push each.
#   3. Branches checked out in another git worktree are synced in place.
#   4. On conflict a branch's merge is ABORTED and skipped — never pushed
#      half-merged. A per-branch summary is printed at the end; the script
#      exits non-zero if any branch had a problem.

set -uo pipefail

MAIN="${MAIN_BRANCH:-main}"
SOURCE="${1:-$(git rev-parse --abbrev-ref HEAD)}"

if [ "$SOURCE" = "$MAIN" ]; then
  echo "ERROR: source branch must differ from '$MAIN'. Pass a feature branch." >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree not clean (we switch branches). Commit or stash first." >&2
  exit 1
fi

echo "Source : $SOURCE"
echo "Target : $MAIN"
git fetch origin

# --- 1) Push source, merge it into main -------------------------------------
git checkout "$SOURCE"
git push origin "$SOURCE" || true
git checkout "$MAIN"
git pull --ff-only origin "$MAIN" || true
if ! git merge --no-edit "$SOURCE"; then
  echo "ERROR: merging '$SOURCE' into '$MAIN' conflicted — resolve manually." >&2
  git merge --abort 2>/dev/null || true
  exit 1
fi
git push origin "$MAIN"

# --- helper: path of the worktree a branch is checked out in (empty if none) -
worktree_of() {
  git worktree list --porcelain | awk -v b="refs/heads/$1" '
    /^worktree /{wt=$2} /^branch /{if ($2==b) print wt}'
}

# --- 2) Propagate main into every other local branch ------------------------
mapfile -t BRANCHES < <(git for-each-ref --format='%(refname:short)' refs/heads/ \
                          | grep -vxE "$MAIN|$SOURCE")

ROOT="$(git rev-parse --show-toplevel)"
declare -a RESULTS
ok=0; bad=0
for b in "${BRANCHES[@]}"; do
  echo ">>> $b"
  wt="$(worktree_of "$b")"
  if [ -n "$wt" ] && [ "$wt" != "$ROOT" ]; then
    # Branch lives in another worktree — operate there.
    if [ -n "$(git -C "$wt" status --porcelain)" ]; then
      RESULTS+=("$b: SKIPPED (worktree $wt dirty)"); bad=$((bad+1)); continue
    fi
    if git -C "$wt" merge --no-edit -m "Sync $MAIN into $b" "$MAIN" >/dev/null 2>&1; then
      if git -C "$wt" push origin "$b" >/dev/null 2>&1; then
        RESULTS+=("$b: OK (worktree)"); ok=$((ok+1))
      else
        RESULTS+=("$b: MERGED but PUSH-FAILED (worktree)"); bad=$((bad+1))
      fi
    else
      git -C "$wt" merge --abort >/dev/null 2>&1 || true
      RESULTS+=("$b: CONFLICT -> aborted (worktree)"); bad=$((bad+1))
    fi
    continue
  fi

  if ! git checkout "$b" >/dev/null 2>&1; then
    RESULTS+=("$b: CHECKOUT-FAILED"); bad=$((bad+1)); continue
  fi
  git pull --no-edit origin "$b" >/dev/null 2>&1
  if [ "$(git ls-files -u | wc -l)" -gt 0 ]; then
    git merge --abort >/dev/null 2>&1; git rebase --abort >/dev/null 2>&1
    RESULTS+=("$b: SKIPPED (remote diverged / pull conflict)"); bad=$((bad+1)); continue
  fi
  if git merge --no-edit -m "Sync $MAIN into $b" "$MAIN" >/dev/null 2>&1; then
    if git push origin "$b" >/dev/null 2>&1; then
      RESULTS+=("$b: OK"); ok=$((ok+1))
    else
      RESULTS+=("$b: MERGED but PUSH-FAILED"); bad=$((bad+1))
    fi
  else
    git merge --abort >/dev/null 2>&1 || true
    RESULTS+=("$b: CONFLICT -> aborted, skipped"); bad=$((bad+1))
  fi
done

git checkout "$SOURCE" >/dev/null 2>&1
echo "============================================"
echo "Back on: $(git rev-parse --abbrev-ref HEAD)"
echo "SYNC SUMMARY (ok=$ok, problems=$bad):"
printf '  %s\n' "${RESULTS[@]}"
[ "$bad" -eq 0 ]
