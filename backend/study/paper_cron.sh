#!/usr/bin/env bash
# Cron wrapper for the paper trader. Safe to fire as often as you like: the
# runner takes an exclusive file lock (no concurrent state mutation) and a
# new-bar guard (does nothing until a 4h bar closes), so over-firing is a no-op.
#
# Install (every 30 min; the runner self-skips between 4h bars):
#   */30 * * * * /home/nageshmadaram/Sterling/backend/study/paper_cron.sh
#
# Inspect:  tail -f <repo>/backend/data/paper/cron.log
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # .../backend
LOG="$HERE/data/paper/cron.log"
mkdir -p "$(dirname "$LOG")"

cd "$HERE"
{
  echo "===== $(date -u '+%Y-%m-%dT%H:%M:%SZ') ====="
  PYTHONWARNINGS=ignore ./.venv/bin/python -m study.paper_trader "$@"
} >> "$LOG" 2>&1
