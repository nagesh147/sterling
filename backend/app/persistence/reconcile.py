"""
ORM-vs-sqlite drift report (Phase 5c monitoring).

The production flip is gated on watching for drift between the raw-sqlite stores
(ground truth) and the SQLAlchemy mirror. reconcile_all() produces a per-store
report; has_drift() collapses it to a go/no-go. Run via scripts/orm_reconcile.py.
"""
from __future__ import annotations

import re
from typing import Dict, Set

from app.persistence import sync

# (mirror store name, sqlite table, key column)
_GENERIC_STORES = [
    ("pnl_history", "pnl_history", "pos_id"),
    ("alerts", "alerts", "id"),
    ("webhooks", "webhooks", "id"),
    ("exchange_configs", "exchange_configs", "id"),
    ("calibration_state", "calibration_state", "underlying"),
    ("derivatives_audit", "derivatives_audit", "audit_id"),
]

# Identifiers only — never interpolate untrusted input into SQL.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_TABLE_COLS: Set[tuple[str, str]] = {(t, k) for _, t, k in _GENERIC_STORES}


def _sqlite_keys(table: str, key_col: str) -> Set[str]:
    if (table, key_col) not in _ALLOWED_TABLE_COLS:
        raise ValueError(f"refusing non-allowlisted table/column: {table!r}.{key_col!r}")
    if not _IDENT_RE.fullmatch(table) or not _IDENT_RE.fullmatch(key_col):
        raise ValueError(f"invalid SQL identifier: {table!r}.{key_col!r}")
    from app.services import db
    if not getattr(db, "_available", False):
        return set()
    try:
        with db._conn() as c:
            # Identifiers cannot be bound as parameters; values are allowlisted above.
            sql = f'SELECT "{key_col}" FROM "{table}"'
            return {str(r[0]) for r in c.execute(sql).fetchall()}
    except Exception:
        return set()


def reconcile_all() -> Dict[str, dict]:
    """Compare every mirrored store against its sqlite source of truth."""
    from app.services import db
    report: Dict[str, dict] = {}
    positions = [{"id": p.get("id"), "status": p.get("status")} for p in db.load_all()]
    report["positions"] = sync.reconcile_positions(positions)
    for store, table, key_col in _GENERIC_STORES:
        report[store] = sync.reconcile_store(store, _sqlite_keys(table, key_col))
    return report


def has_drift(report: Dict[str, dict]) -> bool:
    for store, result in report.items():
        if store == "positions":
            if result:                       # reconcile_positions: non-empty = drift
                return True
        elif result.get("only_sqlite") or result.get("only_orm"):
            return True
    return False
