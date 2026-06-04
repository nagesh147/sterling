"""
orm_mirror — guarded, fail-safe entry point for dual-writing the low-volume
trading-state stores into the SQLAlchemy mirror (Phase 5c).

Every store calls `record(...)` / `delete(...)` with one line. Both are:
  * NO-OP (and import no sqlalchemy) unless settings.use_sqlalchemy is on, and
  * FAIL-SAFE — a mirror error is logged and swallowed so the primary sqlite
    write is never affected.

Market-data caches (candles, ohlcv, iv_*, arrows, hmm_regimes) are intentionally
NOT mirrored — they are high-volume and reproducible. See MIGRATION.md.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _enabled() -> bool:
    try:
        from app.core.config import settings
        return bool(getattr(settings, "use_sqlalchemy", False))
    except Exception:
        return False


def record(store: str, key: str, payload: dict) -> None:
    if not _enabled():
        return
    try:
        from app.persistence.sync import mirror_record
        mirror_record(store, key, payload)
    except Exception as exc:
        log.warning("ORM mirror record(%s/%s) failed (non-fatal): %s", store, key, exc)


def delete(store: str, key: str) -> None:
    if not _enabled():
        return
    try:
        from app.persistence.sync import mirror_record_delete
        mirror_record_delete(store, key)
    except Exception as exc:
        log.warning("ORM mirror delete(%s/%s) failed (non-fatal): %s", store, key, exc)
