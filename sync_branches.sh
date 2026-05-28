#!/bin/bash
set -e

# Fetch all latest remote tracking branches
git fetch origin

# Define branches to sync
branches=(
  "enhancements-scalping"
  "feat/multi-track-scalping"
  "feat/multi-track-scalping-v2"
  "feat/scalping-optimizer-tf"
  "steroid-improvements"
  "strategy-reset"
  "strategy-v2"
)

# Stash any uncommitted changes first
git stash

# Switch to main and merge the fix branch
git checkout main
git pull origin main
git merge fix/scalping-ui-and-engine-polishes -m "Merge fix/scalping-ui-and-engine-polishes into main"
git push origin main

# Loop through all other branches and merge main into them
for branch in "${branches[@]}"; do
  echo "Syncing branch: $branch"
  git checkout "$branch"
  git pull origin "$branch" || true
  git merge main -m "Sync main into $branch" || true
  git push origin "$branch"
done

# Return to original branch
git checkout fix/scalping-ui-and-engine-polishes

# Pop the stash if there were any changes
git stash pop || true

echo "All branches synced successfully!"
