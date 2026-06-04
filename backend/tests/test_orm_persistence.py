"""
ORM PERSISTENCE (Phase 5a) — SQLAlchemy parallel store scaffolding.

Additive and flag-OFF: nothing in the live app uses this yet. Tests run against
an in-memory sqlite — they NEVER touch the 3.2GB live sterling_paper.db.
"""
import pytest

from app.persistence.base import Base, make_engine, resolve_database_url
from app.persistence.session import make_session_factory, session_scope
from app.persistence.models import PositionRow, EquitySnapshotRow
from app.persistence.repositories import PositionRepository, EquitySnapshotRepository


@pytest.fixture
def session_factory():
    engine = make_engine("sqlite://")            # in-memory, isolated
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def test_position_repository_roundtrip(session_factory):
    with session_scope(session_factory) as s:
        repo = PositionRepository(s)
        repo.add(PositionRow(id="P1", underlying="BTC", status="open", data="{}", entry_ts=1, updated_ts=2))
        repo.add(PositionRow(id="P2", underlying="ETH", status="closed", data="{}", entry_ts=1, updated_ts=2))
    with session_scope(session_factory) as s:
        repo = PositionRepository(s)
        assert repo.get("P1").underlying == "BTC"
        assert [p.id for p in repo.list_open()] == ["P1"]


def test_equity_snapshot_repository_latest(session_factory):
    with session_scope(session_factory) as s:
        repo = EquitySnapshotRepository(s)
        repo.add(portfolio_value=10000.0, drawdown=0.05, circuit_breaker_state="ok")
        repo.add(portfolio_value=10500.0)
    with session_scope(session_factory) as s:
        assert EquitySnapshotRepository(s).latest().portfolio_value == 10500.0


def test_default_url_is_never_the_live_db():
    # Safety: the default must not point at the 3.2GB live paper DB.
    assert "sterling_paper.db" not in resolve_database_url()


def test_sqlalchemy_flag_defaults_off():
    from app.core.config import settings
    assert settings.use_sqlalchemy is False
