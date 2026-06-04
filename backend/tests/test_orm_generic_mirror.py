"""
GENERIC MIRROR (Phase 5c) — (store, key)->JSON dual-write across the low-volume
trading-state stores, via app.services.orm_mirror (guarded + fail-safe).

Temp ORM DBs / spies only — never the live sterling_paper.db.
"""
import pytest


def test_generic_record_mirror_and_reconcile(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.persistence import sync
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/orm_gen.db")
    sync.reset_for_tests()
    try:
        sync.mirror_record("alerts", "A1", {"x": 1})
        sync.mirror_record("alerts", "A2", {"x": 2})
        sync.mirror_record("webhooks", "W1", {"y": 1})  # different store, isolated
        # sqlite has A1,A2,A3 → A3 only in sqlite; webhooks unaffected
        assert sync.reconcile_store("alerts", {"A1", "A2", "A3"}) == {
            "only_sqlite": ["A3"], "only_orm": []
        }
        sync.mirror_record_delete("alerts", "A1")
        assert sync.reconcile_store("alerts", {"A2"}) == {"only_sqlite": [], "only_orm": []}
    finally:
        sync.reset_for_tests()


def test_orm_mirror_entrypoint_guarded(monkeypatch):
    from app.core.config import settings
    from app.services import orm_mirror
    from app.persistence import sync
    calls = []
    monkeypatch.setattr(sync, "mirror_record", lambda *a: calls.append(a))
    monkeypatch.setattr(settings, "use_sqlalchemy", False)
    orm_mirror.record("alerts", "A1", {"x": 1})
    assert calls == []                                   # off → no-op
    monkeypatch.setattr(settings, "use_sqlalchemy", True)
    orm_mirror.record("alerts", "A1", {"x": 1})
    assert calls == [("alerts", "A1", {"x": 1})]         # on → mirrors


def test_orm_mirror_errors_are_swallowed(monkeypatch):
    from app.core.config import settings
    from app.services import orm_mirror
    from app.persistence import sync
    monkeypatch.setattr(settings, "use_sqlalchemy", True)

    def _boom(*a):
        raise RuntimeError("orm down")

    monkeypatch.setattr(sync, "mirror_record", _boom)
    monkeypatch.setattr(sync, "mirror_record_delete", _boom)
    orm_mirror.record("alerts", "A1", {"x": 1})   # must not raise
    orm_mirror.delete("alerts", "A1")             # must not raise
