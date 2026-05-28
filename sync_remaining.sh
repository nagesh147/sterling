#!/bin/bash
set -e

# Sync strategy-reset and strategy-v2
branches=(
  "strategy-reset"
  "strategy-v2"
)

for branch in "${branches[@]}"; do
  echo "Syncing branch: $branch"
  git checkout "$branch"
  git pull origin "$branch" || true
  git merge main -m "Sync main into $branch" || true
  git push origin "$branch"
done

# Return to original branch
git checkout fix/scalping-ui-and-engine-polishes
git stash pop || true

echo "Remaining branches in main repo synced."
