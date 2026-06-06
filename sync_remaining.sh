#!/usr/bin/env bash
# DEPRECATED: superseded by ./sync_branches.sh.
#
# This used to resume a partial sync over a hardcoded branch list. The new
# sync_branches.sh auto-discovers branches and is idempotent + resumable, so
# re-running it finishes any partial sync. This shim just forwards to it.
exec "$(dirname "$0")/sync_branches.sh" "$@"
