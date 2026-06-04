"""ReconciliationAgent — diffs internal positions against broker-reported ones.

Pure comparison; the caller supplies both views (internal from paper_store /
pnl, broker from adapter.get_positions). Returns per-symbol discrepancies.
"""
from __future__ import annotations

from typing import Dict, Optional

from app.bus.event_bus import EventBus

_EPS = 1e-9


class ReconciliationAgent:
    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self.bus = bus

    def reconcile(self, internal: Dict[str, float], broker: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        discrepancies: Dict[str, Dict[str, float]] = {}
        for symbol in set(internal) | set(broker):
            i = internal.get(symbol, 0.0)
            b = broker.get(symbol, 0.0)
            if abs(i - b) > _EPS:
                discrepancies[symbol] = {"internal": i, "broker": b}
        return discrepancies
