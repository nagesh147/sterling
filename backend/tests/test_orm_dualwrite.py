"""
ORM DUAL-WRITE (Phase 5b) — mirror + reconcile, guarded by use_sqlalchemy.

The db.py hook is a no-op (no sqlalchemy import) unless the flag is on, and
fail-safe. Tests use temp ORM DBs / spies — never the live sterling_paper.db,
never the real sqlite positions table.
"""
import pytest


def test_mirror_and_reconcile(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.persistence import sync
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/orm.db")
    sync.reset_for_tests()
    try:
        sync.mirror_position_upsert({"id": "P1", "underlying": "BTC", "status": "open", "entry_timestamp_ms": 1})
        sync.mirror_position_upsert({"id": "P2", "underlying": "ETH", "status": "closed", "entry_timestamp_ms": 2})
        # in sync → no discrepancies
        assert sync.reconcile_positions(
            [{"id": "P1", "status": "open"}, {"id": "P2", "status": "closed"}]
        ) == {}
        # drift: sqlite says P1 closed, ORM still open
        assert sync.reconcile_positions(
            [{"id": "P1", "status": "closed"}, {"id": "P2", "status": "closed"}]
        ) == {"P1": {"sqlite": "closed", "orm": "open"}}
    finally:
        sync.reset_for_tests()


def test_mirror_upsert_then_remove(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.persistence import sync
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/orm2.db")
    sync.reset_for_tests()
    try:
        sync.mirror_position_upsert({"id": "P1", "underlying": "BTC", "status": "open", "entry_timestamp_ms": 1})
        sync.mirror_position_remove("P1")
        assert sync.reconcile_positions([]) == {}
    finally:
        sync.reset_for_tests()


def test_db_hook_is_noop_when_flag_off(monkeypatch):
    from app.core.config import settings
    from app.services import db
    from app.persistence import sync
    monkeypatch.setattr(settings, "use_sqlalchemy", False)
    called = []
    monkeypatch.setattr(sync, "mirror_position_upsert", lambda pd: called.append(pd["id"]))
    db._mirror_position_upsert({"id": "X", "underlying": "BTC", "status": "open", "entry_timestamp_ms": 1})
    assert called == []  # flag off → never touches the ORM


def test_db_hook_calls_mirror_when_flag_on(monkeypatch):
    from app.core.config import settings
    from app.services import db
    from app.persistence import sync
    monkeypatch.setattr(settings, "use_sqlalchemy", True)
    called = []
    monkeypatch.setattr(sync, "mirror_position_upsert", lambda pd: called.append(pd["id"]))
    db._mirror_position_upsert({"id": "X", "underlying": "BTC", "status": "open", "entry_timestamp_ms": 1})
    assert called == ["X"]


def test_db_hook_mirror_error_is_swallowed(monkeypatch):
    from app.core.config import settings
    from app.services import db
    from app.persistence import sync
    monkeypatch.setattr(settings, "use_sqlalchemy", True)

    def _boom(pd):
        raise RuntimeError("orm down")

    monkeypatch.setattr(sync, "mirror_position_upsert", _boom)
    # must NOT raise — primary write path is protected
    db._mirror_position_upsert({"id": "X", "underlying": "BTC", "status": "open", "entry_timestamp_ms": 1})
