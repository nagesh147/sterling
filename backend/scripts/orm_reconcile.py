#!/usr/bin/env python
"""
ORM reconciliation CLI (Phase 5c).

Prints the per-store drift report between the raw-sqlite stores and the
SQLAlchemy mirror, and exits 1 if any drift is found — so it can gate the
production flip in CI / a monitoring cron.

Usage (from backend/):
    USE_SQLALCHEMY=true .venv/bin/python -m scripts.orm_reconcile
"""
import json
import sys

from app.persistence.reconcile import reconcile_all, has_drift


def main() -> int:
    report = reconcile_all()
    print(json.dumps(report, indent=2, default=str))
    drift = has_drift(report)
    print("RESULT:", "DRIFT DETECTED" if drift else "IN SYNC")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
