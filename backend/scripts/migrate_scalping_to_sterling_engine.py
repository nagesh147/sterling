"""Idempotent migration for the scalping → Sterling Engine rename.

ONLY the engine CONFIG key is migrated (`scalping_config` → `sterling_engine_config`).

The trading-mode "scalping" and the `[SCALP-...]` position-note tags are deliberately
PRESERVED: they denote the scalping-*style* trading concept (fast-timeframe trailing,
used across directional / cooldown / trailing / derivatives), not the engine identity.
So NO position rows are touched and trailing on existing positions is unaffected.

This migration is optional — `_get_config` already falls back to the legacy key — but
running it populates the new key proactively so the legacy key can eventually be dropped.

Safe to run repeatedly. Prefer running with the backend stopped so a concurrent config
save can't race the copy.

Usage:
    cd backend && PYTHONPATH=. .venv/bin/python3 scripts/migrate_scalping_to_sterling_engine.py
"""
from app.services.db import get_config, set_config

OLD_KEY = "scalping_config"
NEW_KEY = "sterling_engine_config"


def main() -> None:
    new = get_config(NEW_KEY)
    if new:
        print(f"[skip] {NEW_KEY} already present ({len(new)} bytes) — nothing to do")
        return
    old = get_config(OLD_KEY)
    if not old:
        print(f"[skip] no legacy {OLD_KEY} found — fresh install, nothing to migrate")
        return
    set_config(NEW_KEY, old)
    print(f"[ok] copied {OLD_KEY} -> {NEW_KEY} ({len(old)} bytes). Legacy key left intact for rollback.")


if __name__ == "__main__":
    main()
