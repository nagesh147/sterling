"""
ORM RECONCILE (Phase 5c) — drift report orchestration over the mirror.

Uses a temp ORM DB + monkeypatched sqlite sources; never touches the live DB.
"""
import pytest


def test_reconcile_all_detects_drift(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.persistence import sync, reconcile
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/orm.db")
    sync.reset_for_tests()
    try:
        # ORM mirror: position P1 + alert A1
        sync.mirror_position_upsert({"id": "P1", "underlying": "BTC", "status": "open", "entry_timestamp_ms": 1})
        sync.mirror_record("alerts", "A1", {"x": 1})
        from app.services import db
        # sqlite truth: positions P1 + P2 (P2 missing in ORM → drift); alerts A1 (in sync)
        monkeypatch.setattr(db, "load_all", lambda: [{"id": "P1", "status": "open"}, {"id": "P2", "status": "open"}])
        monkeypatch.setattr(reconcile, "_sqlite_keys", lambda t, c: {"A1"} if t == "alerts" else set())
        report = reconcile.reconcile_all()
        assert "P2" in report["positions"]                 # only in sqlite
        assert report["alerts"] == {"only_sqlite": [], "only_orm": []}
        assert reconcile.has_drift(report) is True
    finally:
        sync.reset_for_tests()


def test_reconcile_all_in_sync(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.persistence import sync, reconcile
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/orm2.db")
    sync.reset_for_tests()
    try:
        sync.mirror_position_upsert({"id": "P1", "underlying": "BTC", "status": "open", "entry_timestamp_ms": 1})
        from app.services import db
        monkeypatch.setattr(db, "load_all", lambda: [{"id": "P1", "status": "open"}])
        monkeypatch.setattr(reconcile, "_sqlite_keys", lambda t, c: set())
        report = reconcile.reconcile_all()
        assert reconcile.has_drift(report) is False
    finally:
        sync.reset_for_tests()
