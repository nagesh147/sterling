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


def test_equity_snapshot_mirror(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.persistence import sync
    from app.persistence.base import make_engine
    from app.persistence.session import make_session_factory, session_scope
    from app.persistence.repositories import EquitySnapshotRepository
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/orm_eq.db")
    sync.reset_for_tests()
    try:
        sync.mirror_equity_snapshot(10000.0, drawdown=0.05, circuit_breaker_state="ok")
        sync.mirror_equity_snapshot(10500.0)
        # read it back through a fresh factory on the same file
        factory = make_session_factory(make_engine(f"sqlite:///{tmp_path}/orm_eq.db"))
        with session_scope(factory) as s:
            assert EquitySnapshotRepository(s).latest().portfolio_value == 10500.0
    finally:
        sync.reset_for_tests()


def test_db_equity_hook_guarded(monkeypatch):
    from app.core.config import settings
    from app.services import db
    from app.persistence import sync
    calls = []
    monkeypatch.setattr(sync, "mirror_equity_snapshot", lambda *a: calls.append(a))
    monkeypatch.setattr(settings, "use_sqlalchemy", False)
    db._mirror_equity_snapshot(1.0, None, None)
    assert calls == []                      # off → no-op
    monkeypatch.setattr(settings, "use_sqlalchemy", True)
    db._mirror_equity_snapshot(1.0, 0.1, "ok")
    assert calls == [(1.0, 0.1, "ok")]      # on → mirrors
