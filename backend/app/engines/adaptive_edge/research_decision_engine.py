"""Research-only DecisionEngine adapter for the canonical E2E boundary.

Consumes evaluated evidence and applies recovered F-110 semantics. It never
authorizes risk, creates orders, or submits execution.
"""
from __future__ import annotations

from typing import Callable

from .e2e import DecisionEligibility, PredictionEvidence
from .edge import EdgeAssessment
from .economic import EconomicAssessment
from .feature_engine import FeatureSnapshot
from .f110_entry_gate import EntryDecision, F110Evidence, evaluate_entry


class ResearchDecisionEngine:
    """Adapt recovered F-110 semantics to the E2E DecisionEngine protocol."""

    def __init__(self, evidence_factory: Callable[[FeatureSnapshot, PredictionEvidence, EdgeAssessment, EconomicAssessment], F110Evidence]):
        self._evidence_factory = evidence_factory

    def assess(self, snapshot: FeatureSnapshot, prediction: PredictionEvidence, edge: EdgeAssessment, economics: EconomicAssessment) -> DecisionEligibility:
        evidence = self._evidence_factory(snapshot, prediction, edge, economics)
        option_type = str(edge.inputs.get("option_type", "")).upper()
        decision = evaluate_entry(option_type, evidence)
        eligible = decision is not EntryDecision.NO_TRADE and economics.eligible
        return DecisionEligibility(
            eligible=eligible,
            reason="authorized_research_entry" if eligible else "research_entry_gate_rejected",
            decision_id=f"research-decision:{snapshot.snapshot_id}",
            snapshot_id=snapshot.snapshot_id,
            prediction_id=prediction.prediction_id,
            opportunity_id=edge.opportunity_id,
        )
