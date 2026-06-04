"""Repositories — the data-access surface over the ORM models (Phase 5a).

Keeps query logic in one place per aggregate so callers (and a future dual-write
layer) depend on intent, not raw SQL.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import PositionRow, EquitySnapshotRow


class PositionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: PositionRow) -> PositionRow:
        self.session.add(row)
        self.session.flush()
        return row

    def get(self, position_id: str) -> Optional[PositionRow]:
        return self.session.get(PositionRow, position_id)

    def list_open(self) -> List[PositionRow]:
        return list(self.session.scalars(
            select(PositionRow).where(PositionRow.status == "open")
        ))


class EquitySnapshotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, portfolio_value: float, drawdown: Optional[float] = None,
            circuit_breaker_state: Optional[str] = None) -> EquitySnapshotRow:
        row = EquitySnapshotRow(
            portfolio_value=portfolio_value,
            drawdown=drawdown,
            circuit_breaker_state=circuit_breaker_state,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self) -> Optional[EquitySnapshotRow]:
        return self.session.scalars(
            select(EquitySnapshotRow).order_by(EquitySnapshotRow.id.desc())
        ).first()
