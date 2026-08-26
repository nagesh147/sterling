"""Canonical research path from TrueData event through F-110 order admission.

This module deliberately stops at a CanonicalOrderIntent. Submission remains a
separate gateway boundary requiring the F-110 admission proof and execution
authorization.
"""
from __future__ import annotations

from dataclasses import dataclass

from .f101_f106_pipeline import F101F106PipelineInput, F101F106PipelineResult, evaluate_upstream
from .f107_f110_pipeline import F107F110Input, F107F110Decision, evaluate_f107_f110
from .f110_order_admission import F110OrderAdmission, create_admitted_order
from .f110_admission_proof import create_f110_admission_proof
from .event_boundary import CanonicalMarketEvent


@dataclass(frozen=True)
class TruePathOrderResult:
    upstream: F101F106PipelineResult
    risk_entry: F107F110Decision | None
    admission: F110OrderAdmission
    f110_proof: str | None

    @property
    def order_ready(self) -> bool:
        return self.admission.admitted and self.f110_proof is not None


def build_order_from_canonical_event(
    event: CanonicalMarketEvent,
    *,
    upstream: F101F106PipelineInput,
    risk_entry: F107F110Input,
    selection_id: str,
    side: str,
    intent_version: str,
    created_at: str,
) -> TruePathOrderResult:
    if event.available_at < event.event_time:
        raise ValueError("canonical event violates causal availability boundary")
    upstream_result = evaluate_upstream(upstream)
    if not upstream_result.eligible_for_downstream_execution:
        return TruePathOrderResult(upstream_result, None, F110OrderAdmission(False, None, "upstream_ineligible"), None)
    risk_result = evaluate_f107_f110(risk_entry)
    admission = create_admitted_order(
        risk_result,
        selection_id=selection_id,
        side=side,
        intent_version=intent_version,
        created_at=created_at,
    )
    proof = create_f110_admission_proof(admission.order_intent) if admission.admitted else None
    return TruePathOrderResult(upstream_result, risk_result, admission, proof)
