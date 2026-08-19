"""F-110 research entry conjunction.

Recovered source (Adaptive Order-Flow Options Scalping §35):

    BUY_CE = DataOK ∧ DirectionalEdgeOK ∧ EV>0 ∧ ConservativeEV>0
             ∧ LiquidityOK ∧ SlippageOK ∧ RiskOK
    BUY_PE = the same for PE
    otherwise NO_TRADE

ConservativeEV = Q_q(EV_distribution) with q learned. q is not uniquely
specified, so ConservativeEV is an explicit required input. It is not
invented as a fraction of EV. F-110 stays LOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .e2e import DecisionEligibility, PredictionEvidence
from .economic import EconomicAssessment
from .edge import EdgeAssessment
from .feature_engine import FeatureSnapshot, FeatureStatus


class EntryAction(str, Enum):
    NO_TRADE = "NO_TRADE"
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"


@dataclass(frozen=True)
class EntryDecisionEvidence:
    option_type: str
    conservative_ev: float | None
    directional_edge_ok: bool
    liquidity_ok: bool
    slippage_ok: bool
    risk_ok: bool


@dataclass(frozen=True)
class EntryDecision:
    action: EntryAction
    reason: str
    gates: Mapping[str, bool]
    snapshot_id: str
    prediction_id: str
    opportunity_id: str

    @property
    def eligible(self) -> bool:
        return self.action is not EntryAction.NO_TRADE


def snapshot_data_ok(snapshot: FeatureSnapshot) -> bool:
    return all(
        status in {FeatureStatus.VALID, FeatureStatus.NOT_APPLICABLE}
        for status in snapshot.statuses.values()
    )


def evaluate_entry_decision(
    snapshot: FeatureSnapshot,
    prediction: PredictionEvidence,
    edge: EdgeAssessment,
    economics: EconomicAssessment,
    evidence: EntryDecisionEvidence,
) -> EntryDecision:
    if prediction.snapshot_id != snapshot.snapshot_id:
        raise ValueError("prediction snapshot identity mismatch")
    if edge.opportunity_id != prediction.opportunity_id:
        raise ValueError("edge opportunity identity mismatch")
    if evidence.option_type not in {"CE", "PE"}:
        raise ValueError("option_type must be CE or PE")

    gates = {
        "DataOK": snapshot_data_ok(snapshot),
        "DirectionalEdgeOK": evidence.directional_edge_ok,
        "EV": economics.expected_net_value > 0 and economics.eligible,
        "ConservativeEV": evidence.conservative_ev is not None and evidence.conservative_ev > 0,
        "LiquidityOK": evidence.liquidity_ok,
        "SlippageOK": evidence.slippage_ok,
        "RiskOK": evidence.risk_ok,
    }
    if evidence.conservative_ev is None:
        reason = "missing_conservative_ev"
        action = EntryAction.NO_TRADE
    elif not all(gates.values()):
        reason = "entry_conjunction_failed:" + ",".join(name for name, ok in gates.items() if not ok)
        action = EntryAction.NO_TRADE
    else:
        reason = "entry_conjunction_passed"
        action = EntryAction.BUY_CE if evidence.option_type == "CE" else EntryAction.BUY_PE
    return EntryDecision(
        action=action,
        reason=reason,
        gates=gates,
        snapshot_id=snapshot.snapshot_id,
        prediction_id=prediction.prediction_id,
        opportunity_id=prediction.opportunity_id,
    )


class ConjunctionDecisionEngine:
    """DecisionEngine adapter. ConservativeEV is injected, never inferred."""

    def __init__(self, evidence: EntryDecisionEvidence) -> None:
        self._evidence = evidence

    def assess(
        self,
        snapshot: FeatureSnapshot,
        prediction: PredictionEvidence,
        edge: EdgeAssessment,
        economics: EconomicAssessment,
    ) -> DecisionEligibility:
        decision = evaluate_entry_decision(snapshot, prediction, edge, economics, self._evidence)
        return DecisionEligibility(
            eligible=decision.eligible,
            reason=decision.reason,
            decision_id=f"DEC-{snapshot.snapshot_id}",
            snapshot_id=snapshot.snapshot_id,
            prediction_id=prediction.prediction_id,
            opportunity_id=prediction.opportunity_id,
        )
