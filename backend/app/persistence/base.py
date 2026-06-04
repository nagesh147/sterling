"""SQLAlchemy Base + engine factory (Postgres-ready, no SQLite-only SQL)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def resolve_database_url() -> str:
    """Return the SQLAlchemy URL.

    Precedence: settings.database_url → a DEDICATED sqlite file under backend/.
    Never defaults to the live sterling_paper.db (Phase 5b wires that explicitly).
    Set DATABASE_URL to a postgresql:// URL for production.
    """
    try:
        from app.core.config import settings
        url = (getattr(settings, "database_url", "") or "").strip()
    except Exception:
        url = ""
    if url:
        return url
    backend_dir = Path(__file__).resolve().parents[2]
    return f"sqlite:///{backend_dir / 'sterling_orm.db'}"


def make_engine(url: Optional[str] = None, echo: bool = False) -> Engine:
    url = url or resolve_database_url()
    kwargs: dict = {"echo": echo, "future": True}
    if url in ("sqlite://", "sqlite:///:memory:"):
        # Share one in-memory DB across connections (tests).
        from sqlalchemy.pool import StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)
