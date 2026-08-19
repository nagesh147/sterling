"""Compose a projected PositionState with A177 protection and A126 lifecycle.

This is an integration boundary, not new strategy mathematics.

    PositionState
        → ProtectionEngine (caller-supplied policy; F-112 stays LOCKED)
        → LifecycleEvidence
        → A126LifecycleEngine (F-111 stays LOCKED)
        → optional flatten through AdaptiveEdgeExecutionPath

F-113 is only the post-exit semantic boundary: outcome is finalized and the
previous risk authorization cannot be reused. No re-entry score is invented.
"""
from __future__ import annotations

from dataclasses import dataclass

from .broker_event_mapper import BrokerExecutionEvent
from .e2e import LifecycleEvaluation, PositionState
from .execution_adapter import CanonicalOrderIntent
from .execution_path import AdaptiveEdgeExecutionPath, ExecutionPathResult, ExecutionStep
from .lifecycle_engine import A126LifecycleEngine, LifecycleAction, LifecycleEvidence
from .protection import ProtectionDecision, ProtectionEngine, ProtectionPolicy
from .research_session import a126_session_cutoff_reached


EXIT_ACTIONS = {
    LifecycleAction.EXIT_HARD_STOP.value,
    LifecycleAction.EXIT_THESIS_INVALID.value,
    LifecycleAction.EXIT_PROFIT_PROTECTION.value,
    LifecycleAction.EXIT_ECONOMIC_COLLAPSE.value,
    LifecycleAction.EXIT_SESSION_CUTOFF.value,
    LifecycleAction.EXIT_EMERGENCY.value,
}


class PostExitError(ValueError):
    """Raised when a post-exit semantic boundary is violated."""


@dataclass(frozen=True)
class ManagedPositionTick:
    position: PositionState
    protection: ProtectionDecision
    lifecycle: LifecycleEvaluation
    exit_required: bool


class ManagedPosition:
    """Supervise one projected position until its outcome is finalized."""

    def __init__(
        self,
        position: PositionState,
        *,
        side: str,
        entry_price: float,
        policy: ProtectionPolicy,
        authorization_id: str,
        entry_order: CanonicalOrderIntent | None = None,
    ) -> None:
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if not authorization_id:
            raise ValueError("authorization_id is required")
        if position.quantity <= 0:
            raise ValueError("managed position requires a positive open quantity")
        self._position = position
        self._side = side
        self._entry_price = float(entry_price)
        self._authorization_id = authorization_id
        self._entry_order = entry_order
        self._protection = ProtectionEngine(policy, side=side, entry_price=self._entry_price)
        self._lifecycle = A126LifecycleEngine(position.position_id)
        self._finalized = False
        self._consumed_authorizations: set[str] = set()
        self._exit_action: str | None = None
        self._last_protection: ProtectionDecision | None = None

    @classmethod
    def from_execution(
        cls,
        executed: ExecutionPathResult,
        *,
        policy: ProtectionPolicy,
    ) -> "ManagedPosition":
        fill_price = executed.execution.fill_price
        if fill_price is None or fill_price <= 0:
            raise ValueError("execution fill_price is required to manage a position")
        authorization_id = executed.order.authorization_id or executed.order.causal_parent_ids[0]
        return cls(
            executed.position,
            side=executed.order.side,
            entry_price=fill_price,
            policy=policy,
            authorization_id=authorization_id,
            entry_order=executed.order,
        )

    @property
    def position(self) -> PositionState:
        return self._position

    @property
    def outcome_finalized(self) -> bool:
        return self._finalized

    @property
    def authorization_id(self) -> str:
        return self._authorization_id

    def on_mark(
        self,
        mark: float,
        event_time: str,
        *,
        economic_edge_valid: bool = True,
        thesis_valid: bool = True,
        is_emergency: bool = False,
        data_certain: bool = True,
        liquidity_healthy: bool = True,
        persistence_evidence_valid: bool = False,
        persistence_decayed: bool = False,
    ) -> ManagedPositionTick:
        if self._finalized:
            return ManagedPositionTick(
                position=self._position,
                protection=self._last_protection or self._protection.update(mark),
                lifecycle=LifecycleEvaluation(
                    evaluation_id=f"eval-{self._position.position_id}-final",
                    position_id=self._position.position_id,
                    lifecycle_version="A126-v1.0",
                    lifecycle_state="FLAT",
                    protection_state=self._lifecycle.protection_state.value,
                    action="NO_ACTION",
                    reason="outcome_finalized",
                    evaluated_at=event_time,
                ),
                exit_required=False,
            )

        protection = self._protection.update(mark)
        self._last_protection = protection
        evidence = LifecycleEvidence(
            protective_stop_hit=protection.reason == "protective_stop_hit",
            profit_lock_hit=protection.reason == "profit_lock_hit",
            trailing_hit=protection.reason == "trailing_hit",
            session_cutoff_reached=a126_session_cutoff_reached(event_time),
            hard_risk_breached=_hard_risk_breached(self._position, self._side, mark),
            economic_edge_valid=economic_edge_valid,
            thesis_valid=thesis_valid,
            is_emergency=is_emergency,
            data_certain=data_certain,
            liquidity_healthy=liquidity_healthy,
            persistence_evidence_valid=persistence_evidence_valid,
            persistence_decayed=persistence_decayed,
        )
        lifecycle = self._lifecycle.evaluate_with_evidence(self._position, evidence, event_time)
        exit_required = lifecycle.action in EXIT_ACTIONS
        if exit_required:
            self._finalize(lifecycle.action)
        return ManagedPositionTick(
            position=self._position,
            protection=protection,
            lifecycle=lifecycle,
            exit_required=exit_required,
        )

    def flatten(
        self,
        path: AdaptiveEdgeExecutionPath,
        *,
        fill_price: float,
        event_time: str,
    ) -> ExecutionStep:
        if not self._finalized:
            raise PostExitError("outcome not finalized")
        if self._position.quantity <= 0:
            raise PostExitError("position already flat")
        close_side = "SELL" if self._side == "BUY" else "BUY"
        selection_id = self._entry_order.selection_id if self._entry_order else f"SEL-{self._position.position_id}"
        close = CanonicalOrderIntent(
            order_intent_id=f"EXIT-{self._position.position_id}",
            selection_id=selection_id,
            instrument_id=self._position.instrument_id,
            side=close_side,
            quantity=self._position.quantity,
            intent_version="exit-v1",
            idempotency_key=f"IDEM-EXIT-{self._position.position_id}",
            created_at=event_time,
            authorization_id=self._authorization_id,
            causal_parent_ids=(self._authorization_id, self._position.position_id),
        )
        path.submit(close)
        step = path.receive_and_project(
            BrokerExecutionEvent(
                broker_event_id=f"BE-EXIT-{self._position.position_id}",
                order_intent_id=close.order_intent_id,
                broker_status="FILLED",
                event_time=event_time,
                filled_quantity=close.quantity,
                fill_price=fill_price,
            ),
            instrument_id=self._position.instrument_id,
            side=self._side,
            order_side_map={close.order_intent_id: close_side},
            position_id=self._position.position_id,
        )
        self._position = step.position
        return step

    def assert_independent_opportunity(self, authorization_id: str) -> None:
        if authorization_id in self._consumed_authorizations:
            raise PostExitError("previous risk authorization cannot be reused")

    def finalize_outcome(self, action: str) -> None:
        """Mark the outcome finalized without inventing a re-entry score."""
        self._finalize(action)

    def _finalize(self, action: str) -> None:
        self._finalized = True
        self._exit_action = action
        self._consumed_authorizations.add(self._authorization_id)


def _hard_risk_breached(position: PositionState, side: str, mark: float) -> bool:
    if position.risk_boundary is None:
        return False
    if side == "BUY":
        return mark <= position.risk_boundary
    return mark >= position.risk_boundary
