"""
ORM models mirroring existing raw-sqlite tables (Phase 5a).

Table names + columns match app/services/db.py so a future dual-write (Phase 5b)
reads/writes the same shapes. Two representative tables are mirrored here; the
remaining tables follow the same pattern.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class PositionRow(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    underlying: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    entry_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    # Columns added via ALTER TABLE in db.py:
    greeks_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notional: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    slippage_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class EquitySnapshotRow(Base):
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    circuit_breaker_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MirroredRecord(Base):
    """Generic (store, key) → JSON mirror for the low-volume trading-state stores.

    A uniform parity/audit mirror so every store can dual-write with a one-line
    hook (see app/services/orm_mirror.py). First-class entities (positions,
    equity_snapshots) keep their own typed tables; any store here can be promoted
    to a typed model when it becomes authoritative.
    """
    __tablename__ = "mirrored_records"

    store: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    updated_ts: Mapped[int] = mapped_column(Integer, nullable=False)
