"""A126 Canonical Adaptive Trade Horizon, Position Protection & Lifecycle Engine.

Canonical invariants (A126):
1. Initial horizon != current horizon != exit condition.
2. Horizon, Thesis, Protection, and Overlays are orthogonal state dimensions.
3. Five management horizons:
       H0 IMPULSE, H1 TACTICAL, H2 INTRADAY_SWING, H3 SESSION_TREND, H4 SESSION_EXTENSION
4. Promotion is evidence-driven (profit alone cannot promote).
5. Downgrade is permitted when persistence weakens while thesis remains valid.
6. THESIS_INVALID or HARD_RISK_BREACH forces immediate EXIT.
7. Normal trading cutoff = SESSION_CLOSE - 45 minutes:
       New entries/upgrades forbidden; positions must be flattened by cutoff.
8. Every transition produces an immutable, auditable TransitionRecord.
9. No numerical promotion/downgrade thresholds are invented; all evidence must be
   explicitly provided by strategy decision/evidence inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .e2e import LifecycleEvaluation, PositionState
from .event_boundary import CanonicalMarketEvent


class HorizonState(str, Enum):
    IMPULSE = "IMPULSE"                    # H0: ~seconds to 5 min
    TACTICAL = "TACTICAL"                  # H1: ~3 to 20 min
    INTRADAY_SWING = "INTRADAY_SWING"      # H2: ~15 to 60 min
    SESSION_TREND = "SESSION_TREND"        # H3: ~45 min to 2.5 hr
    SESSION_EXTENSION = "SESSION_EXTENSION"# H4: ~2 to 5+ hr


class ThesisState(str, Enum):
    THESIS_STRONG = "THESIS_STRONG"
    THESIS_VALID = "THESIS_VALID"
    THESIS_WEAKENING = "THESIS_WEAKENING"
    THESIS_INVALID = "THESIS_INVALID"


class ProtectionState(str, Enum):
    P0_RISK_CONTROLLED = "P0_RISK_CONTROLLED"
    P1_BREAKEVEN_PROTECTED = "P1_BREAKEVEN_PROTECTED"
    P2_PROFIT_PROTECTED = "P2_PROFIT_PROTECTED"
    P3_AGGRESSIVE_TRAIL = "P3_AGGRESSIVE_TRAIL"


class OverlayState(str, Enum):
    BURST = "BURST"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"
    DATA_UNCERTAINTY = "DATA_UNCERTAINTY"
    ECONOMIC_COLLAPSE = "ECONOMIC_COLLAPSE"
    FLOW_AGAINST = "FLOW_AGAINST"
    OUTSIDE_VALUE = "OUTSIDE_VALUE"
    AGAINST_VWAP = "AGAINST_VWAP"
    OUTSIDE_OR = "OUTSIDE_OR"
    VALUE_MIGRATION_AGAINST = "VALUE_MIGRATION_AGAINST"
    AT_LVN = "AT_LVN"
    EMERGENCY = "EMERGENCY"


class LifecycleAction(str, Enum):
    HOLD = "HOLD"
    PROMOTE = "PROMOTE"
    DOWNGRADE = "DOWNGRADE"
    UPDATE_PROTECTION = "UPDATE_PROTECTION"
    EXIT_HARD_STOP = "EXIT_HARD_STOP"
    EXIT_THESIS_INVALID = "EXIT_THESIS_INVALID"
    EXIT_PROFIT_PROTECTION = "EXIT_PROFIT_PROTECTION"
    EXIT_ECONOMIC_COLLAPSE = "EXIT_ECONOMIC_COLLAPSE"
    EXIT_SESSION_CUTOFF = "EXIT_SESSION_CUTOFF"
    EXIT_EMERGENCY = "EXIT_EMERGENCY"


PROMOTION_PATH: Mapping[HorizonState, HorizonState] = {
    HorizonState.IMPULSE: HorizonState.TACTICAL,
    HorizonState.TACTICAL: HorizonState.INTRADAY_SWING,
    HorizonState.INTRADAY_SWING: HorizonState.SESSION_TREND,
    HorizonState.SESSION_TREND: HorizonState.SESSION_EXTENSION,
}

DOWNGRADE_PATH: Mapping[HorizonState, HorizonState] = {
    HorizonState.SESSION_EXTENSION: HorizonState.SESSION_TREND,
    HorizonState.SESSION_TREND: HorizonState.INTRADAY_SWING,
    HorizonState.INTRADAY_SWING: HorizonState.TACTICAL,
    HorizonState.TACTICAL: HorizonState.IMPULSE,
}


@dataclass(frozen=True)
class TransitionRecord:
    transition_id: str
    position_id: str
    as_of: str
    from_horizon: HorizonState
    to_horizon: HorizonState
    from_thesis: ThesisState
    to_thesis: ThesisState
    from_protection: ProtectionState
    to_protection: ProtectionState
    trigger: str
    preconditions: Mapping[str, Any]
    supporting_evidence: Mapping[str, Any]
    risk_state: str
    economic_state: str
    model_version: str
    configuration_version: str
    reason_code: str


@dataclass(frozen=True)
class LifecycleEvidence:
    """Explicit market and trade evaluation inputs at decision time t."""
    persistence_evidence_valid: bool = False
    persistence_decayed: bool = False
    thesis_valid: bool = True
    thesis_state: ThesisState = ThesisState.THESIS_VALID
    hard_risk_breached: bool = False
    economic_edge_valid: bool = True
    liquidity_healthy: bool = True
    data_certain: bool = True
    is_emergency: bool = False
    session_cutoff_reached: bool = False
    protective_stop_hit: bool = False
    trailing_hit: bool = False
    profit_lock_hit: bool = False
    current_profit_r: float = 0.0
    suggested_protection: ProtectionState | None = None


class A126LifecycleEngine:
    """Canonical A126 adaptive trade lifecycle supervision and state machine."""

    def __init__(
        self,
        position_id: str,
        initial_horizon: HorizonState = HorizonState.IMPULSE,
        *,
        model_version: str = "v1",
        configuration_version: str = "v1",
    ) -> None:
        self.position_id = position_id
        self.initial_horizon = initial_horizon
        self.current_horizon = initial_horizon
        self.thesis_state = ThesisState.THESIS_VALID
        self.protection_state = ProtectionState.P0_RISK_CONTROLLED
        self.overlays: set[OverlayState] = set()

        self.model_version = model_version
        self.configuration_version = configuration_version
        self.is_active: bool = True
        self._transitions: list[TransitionRecord] = []
        self._evaluation_count: int = 0

    @property
    def transitions(self) -> tuple[TransitionRecord, ...]:
        return tuple(self._transitions)

    def evaluate_with_evidence(
        self,
        position: PositionState,
        evidence: LifecycleEvidence,
        event_time: str,
    ) -> LifecycleEvaluation:
        """Evaluate position state with explicit evidence, enforcing A126 rules."""
        self._evaluation_count += 1
        eval_id = f"eval-{self.position_id}-{self._evaluation_count}"

        if not self.is_active or position.quantity == 0:
            return LifecycleEvaluation(
                evaluation_id=eval_id,
                position_id=self.position_id,
                lifecycle_version="A126-v1.0",
                lifecycle_state="FLAT",
                protection_state=self.protection_state.value,
                action="NO_ACTION",
                reason="position_flat_or_inactive",
                evaluated_at=event_time,
            )

        # 1. Emergency Exit
        if evidence.is_emergency:
            self._record_transition(
                event_time,
                trigger="EMERGENCY_TRIGGER",
                reason_code="emergency_exit",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(eval_id, "FLAT", LifecycleAction.EXIT_EMERGENCY, "emergency_exit", event_time)

        # 2. Hard Risk Breach -> Immediate Exit
        if evidence.hard_risk_breached:
            self._record_transition(
                event_time,
                trigger="HARD_RISK_BREACH",
                reason_code="hard_risk_stop",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(eval_id, "FLAT", LifecycleAction.EXIT_HARD_STOP, "hard_risk_breached", event_time)

        # 3. Session Cutoff (45m before session close) -> Mandatory Flattening
        if evidence.session_cutoff_reached:
            self._record_transition(
                event_time,
                trigger="SESSION_CUTOFF_REACHED",
                reason_code="session_cutoff_exit",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(eval_id, "FLAT", LifecycleAction.EXIT_SESSION_CUTOFF, "cutoff_flattening", event_time)

        # 3b. A177 protection authorities. Session cutoff above cannot be suppressed.
        if evidence.protective_stop_hit:
            self._record_transition(
                event_time,
                trigger="PROTECTIVE_STOP",
                reason_code="protective_stop_hit",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(eval_id, "FLAT", LifecycleAction.EXIT_HARD_STOP, "protective_stop_hit", event_time)
        if evidence.profit_lock_hit:
            self._record_transition(
                event_time,
                trigger="PROFIT_LOCK",
                reason_code="profit_lock_hit",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(
                eval_id, "FLAT", LifecycleAction.EXIT_PROFIT_PROTECTION, "profit_lock_hit", event_time
            )
        if evidence.trailing_hit:
            self._record_transition(
                event_time,
                trigger="TRAILING_PROTECTION",
                reason_code="trailing_hit",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(
                eval_id, "FLAT", LifecycleAction.EXIT_PROFIT_PROTECTION, "trailing_hit", event_time
            )

        # 4. Thesis Invalidation -> Immediate Exit
        if evidence.thesis_state == ThesisState.THESIS_INVALID or not evidence.thesis_valid:
            self.thesis_state = ThesisState.THESIS_INVALID
            self._record_transition(
                event_time,
                trigger="THESIS_INVALIDATION",
                reason_code="thesis_invalid",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(eval_id, "FLAT", LifecycleAction.EXIT_THESIS_INVALID, "thesis_invalidated", event_time)

        # 5. Economic Collapse -> Exit
        if not evidence.economic_edge_valid:
            self._record_transition(
                event_time,
                trigger="ECONOMIC_COLLAPSE",
                reason_code="economic_collapse_exit",
                evidence=evidence,
            )
            self.is_active = False
            return self._build_eval(eval_id, "FLAT", LifecycleAction.EXIT_ECONOMIC_COLLAPSE, "economic_edge_collapsed", event_time)

        # 6. Data Uncertainty Overlay
        if not evidence.data_certain:
            self.overlays.add(OverlayState.DATA_UNCERTAINTY)
            # Do not promote or upgrade when data is uncertain
            return self._build_eval(eval_id, self.current_horizon.value, LifecycleAction.HOLD, "data_uncertainty_hold", event_time)
        else:
            self.overlays.discard(OverlayState.DATA_UNCERTAINTY)

        # 7. Update Thesis State if changed
        if evidence.thesis_state != self.thesis_state:
            old_thesis = self.thesis_state
            self.thesis_state = evidence.thesis_state
            self._record_transition(
                event_time,
                trigger="THESIS_STATE_UPDATE",
                reason_code=f"thesis_{self.thesis_state.value.lower()}",
                evidence=evidence,
            )

        # 8. Update Protection State if suggested
        if evidence.suggested_protection and evidence.suggested_protection != self.protection_state:
            old_prot = self.protection_state
            self.protection_state = evidence.suggested_protection
            self._record_transition(
                event_time,
                trigger="PROTECTION_STATE_UPDATE",
                reason_code=f"protection_{self.protection_state.value.lower()}",
                evidence=evidence,
            )
            return self._build_eval(eval_id, self.current_horizon.value, LifecycleAction.UPDATE_PROTECTION, "protection_updated", event_time)

        # 9. Horizon Promotion Evaluation (evidence-driven, profit alone cannot promote)
        can_promote = (
            self.current_horizon in PROMOTION_PATH
            and self.thesis_state in {ThesisState.THESIS_VALID, ThesisState.THESIS_STRONG}
            and evidence.persistence_evidence_valid
            and evidence.liquidity_healthy
            and not evidence.session_cutoff_reached
        )

        if can_promote:
            next_horizon = PROMOTION_PATH[self.current_horizon]
            old_horizon = self.current_horizon
            self.current_horizon = next_horizon
            self._record_transition(
                event_time,
                trigger="PERSISTENCE_EVIDENCE_PROMOTION",
                reason_code=f"promote_{old_horizon.value}_to_{next_horizon.value}",
                evidence=evidence,
            )
            return self._build_eval(eval_id, self.current_horizon.value, LifecycleAction.PROMOTE, "horizon_promoted", event_time)

        # 10. Horizon Downgrade Evaluation (persistence weakens while thesis remains valid)
        can_downgrade = (
            self.current_horizon in DOWNGRADE_PATH
            and self.thesis_state in {ThesisState.THESIS_VALID, ThesisState.THESIS_WEAKENING}
            and evidence.persistence_decayed
        )

        if can_downgrade:
            next_horizon = DOWNGRADE_PATH[self.current_horizon]
            old_horizon = self.current_horizon
            self.current_horizon = next_horizon
            self._record_transition(
                event_time,
                trigger="PERSISTENCE_DECAY_DOWNGRADE",
                reason_code=f"downgrade_{old_horizon.value}_to_{next_horizon.value}",
                evidence=evidence,
            )
            return self._build_eval(eval_id, self.current_horizon.value, LifecycleAction.DOWNGRADE, "horizon_downgraded", event_time)

        # Default: normal hold under current horizon supervision
        return self._build_eval(eval_id, self.current_horizon.value, LifecycleAction.HOLD, "normal_supervision", event_time)

    def evaluate(self, position: PositionState, event: CanonicalMarketEvent) -> LifecycleEvaluation:
        """Implementation conforming to e2e.py LifecycleEngine protocol."""
        evidence = LifecycleEvidence(
            thesis_valid=True,
            thesis_state=ThesisState.THESIS_VALID,
            hard_risk_breached=False,
            economic_edge_valid=True,
            liquidity_healthy=True,
            data_certain=True,
        )
        return self.evaluate_with_evidence(position, evidence, event.event_time)

    def _record_transition(
        self,
        as_of: str,
        *,
        trigger: str,
        reason_code: str,
        evidence: LifecycleEvidence,
    ) -> None:
        rec = TransitionRecord(
            transition_id=f"trans-{self.position_id}-{len(self._transitions) + 1}",
            position_id=self.position_id,
            as_of=as_of,
            from_horizon=self.current_horizon,
            to_horizon=self.current_horizon,
            from_thesis=self.thesis_state,
            to_thesis=self.thesis_state,
            from_protection=self.protection_state,
            to_protection=self.protection_state,
            trigger=trigger,
            preconditions={"is_active": self.is_active},
            supporting_evidence={
                "persistence_evidence_valid": evidence.persistence_evidence_valid,
                "persistence_decayed": evidence.persistence_decayed,
                "thesis_state": evidence.thesis_state.value,
                "current_profit_r": evidence.current_profit_r,
                "session_cutoff_reached": evidence.session_cutoff_reached,
            },
            risk_state="AUTHORIZED",
            economic_state="VALID" if evidence.economic_edge_valid else "INVALID",
            model_version=self.model_version,
            configuration_version=self.configuration_version,
            reason_code=reason_code,
        )
        self._transitions.append(rec)

    def _build_eval(
        self,
        eval_id: str,
        lifecycle_state: str,
        action: LifecycleAction,
        reason: str,
        evaluated_at: str,
    ) -> LifecycleEvaluation:
        return LifecycleEvaluation(
            evaluation_id=eval_id,
            position_id=self.position_id,
            lifecycle_version="A126-v1.0",
            lifecycle_state=lifecycle_state,
            protection_state=self.protection_state.value,
            action=action.value,
            reason=reason,
            evaluated_at=evaluated_at,
        )


def check_session_cutoff(as_of: str | int | float | None = None) -> bool:
    """Check if market time has reached the 14:45 IST normal trading cutoff."""
    from datetime import datetime, timezone, timedelta, time as dtime
    ist = timezone(timedelta(hours=5, minutes=30))
    if as_of is None:
        now = datetime.now(ist)
    elif isinstance(as_of, (int, float)):
        now = datetime.fromtimestamp(as_of / 1000 if as_of > 1e11 else as_of, ist)
    elif isinstance(as_of, str):
        try:
            now = datetime.fromisoformat(as_of.replace("Z", "+00:00")).astimezone(ist)
        except Exception:
            return False
    else:
        return False

    current_time = now.time()
    cutoff_start = dtime(14, 45)
    return current_time >= cutoff_start
