"""F-112 research protection envelope.

Builds a monotonic effective protection boundary from explicit caller policy.
It deliberately does not promote any numeric parameter to production status.
"""
from __future__ import annotations

from dataclasses import dataclass

from .protection import ProtectionDecision, ProtectionEngine, ProtectionPolicy


@dataclass(frozen=True)
class ProtectionEnvelopeState:
    effective_stop: float | None
    favorable_extreme: float
    lock_active: bool


class F112ProtectionEnvelope:
    def __init__(self, policy: ProtectionPolicy, *, side: str, entry_price: float) -> None:
        self.engine = ProtectionEngine(policy, side=side, entry_price=entry_price)
        self.side = side
        self._effective_stop: float | None = None

    def update(self, mark: float) -> tuple[ProtectionDecision, ProtectionEnvelopeState]:
        decision = self.engine.update(mark)
        candidates = [x for x in (decision.stop_price, decision.trail_price, decision.lock_price) if x is not None]
        if candidates:
            candidate = max(candidates) if self.side == "BUY" else min(candidates)
            if self._effective_stop is None:
                self._effective_stop = candidate
            elif self.side == "BUY":
                self._effective_stop = max(self._effective_stop, candidate)
            else:
                self._effective_stop = min(self._effective_stop, candidate)
        state = ProtectionEnvelopeState(
            effective_stop=self._effective_stop,
            favorable_extreme=decision.extreme,
            lock_active=decision.lock_active,
        )
        return decision, state
