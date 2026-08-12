from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.claim_statistics import (
    CorrectionStatus,
    StatisticalValidityContract,
)
from app.engines.adaptive_edge.decision_audit import (
    AuditChainError,
    AuditLink,
    DecisionAuditRecord,
    append_audit_record,
)
from app.engines.adaptive_edge.deployment_gate import (
    DeploymentGateError,
    GateStatus,
    assemble_deployment_readiness,
)
from app.engines.adaptive_edge.end_to_end_gate import (
    ChainEvent,
    ChainStage,
    EndToEndGateError,
    validate_causal_chain,
    validate_no_execution_without_authorization,
)
from app.engines.adaptive_edge.execution_accounting_integration import (
    FillEvent as AccountingFill,
    derive_accounting_event,
    derive_position_effect,
)
from app.engines.adaptive_edge.execution_boundary import (
    ExecutionBoundaryError,
    OrderIntent,
    authorize_order,
    record_fill,
    record_submission,
)
from app.engines.adaptive_edge.final_holdout import (
    FinalHoldoutEvidence,
    HoldoutCandidate,
)
from app.engines.adaptive_edge.oos_claims import (
    ClaimStatus,
    EvaluationEvidence,
    TestUseEvent,
    assess_claim,
)
from app.engines.adaptive_edge.operational_controls import (
    HealthState,
    OperationalControlDecision,
    OperationalObservation,
    SafetyAction,
    apply_operational_control,
)
from app.engines.adaptive_edge.operational_state import (
    OperationalState,
    OperationalTradingState,
    TradingPermissions,
    validate_operational_trading_state,
)
from app.engines.adaptive_edge.promotion_boundary import (
    PromotionDecision,
    assemble_promotion_eligibility,
)
from app.engines.adaptive_edge.recovery_resume import (
    RecoveryDecision,
    RecoveryState,
    ResumeAuthorization,
    authorize_resume,
)
from app.engines.adaptive_edge.research_selection import (
    CandidateEvaluation,
    ResearchSelectionRegistry,
)
from app.engines.adaptive_edge.statistical_uncertainty import (
    DependenceClass,
    DependenceUnit,
    UncertaintyEvidence,
    UncertaintySpecification,
)

DT = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)


def evidence():
    return EvaluationEvidence(
        evaluation_id="eval-1",
        candidate_id="cand-1",
        code_version="code-1",
        feature_version="feature-1",
        label_version="label-1",
        execution_version="exec-1",
        boundary_id="holdout-1",
        result_fingerprint="result-1",
    )


def candidate(*, observed=False, influenced=False):
    return CandidateEvaluation(
        candidate_id="cand-1",
        evaluation_id="eval-1",
        code_version="code-1",
        feature_version="feature-1",
        label_version="label-1",
        execution_version="exec-1",
        parameter_fingerprint="params-1",
        result_fingerprint="result-1",
        test_observed=observed,
        selection_influenced=influenced,
    )


def holdout():
    return FinalHoldoutEvidence.assemble(
        "holdout-1",
        "eval-1",
        HoldoutCandidate("cand-1", "eval-1", "result-1", False, False),
        "dataset-1",
        "claim-1",
    )


def stats():
    return StatisticalValidityContract(
        evaluation_id="eval-1",
        research_registry_fingerprint="registry-1",
        candidate_population_size=3,
        correction_status=CorrectionStatus.APPLIED,
        correction_method_id="method-1",
        significance_level=0.05,
        adjusted_claim=True,
    )


def test_a47_claim_is_contaminated_by_recorded_test_use():
    claim = assess_claim(
        evidence(),
        test_use_events=(TestUseEvent("eval-1", "event-1", "research review", ("cand-1",)),),
        claim_id="claim-1",
    )
    assert claim.status is ClaimStatus.CONTAMINATED


def test_a48_preserves_cycle_level_evidence():
    from app.engines.adaptive_edge.evaluation_evidence import CycleEvaluationResult, EvaluationEvidenceSet

    cycle = CycleEvaluationResult(
        cycle_id="cycle-1", evaluation_id="eval-1", candidate_id="cand-1",
        code_version="code", feature_version="feature", label_version="label", execution_version="exec",
        train_boundary_id="train", validation_boundary_id="validation", test_boundary_id="test",
        observation_count=10, independent_episode_count=8,
    )
    evidence_set = EvaluationEvidenceSet.build((cycle,))
    assert evidence_set.total_observations == 10
    assert evidence_set.total_independent_episodes == 8
    assert evidence_set.fingerprint


def test_a49_uncertainty_requires_explicit_dependence_specification():
    units = (DependenceUnit("u1", "cycle-1", "episode-1", "1", "2", DependenceClass.SERIAL),)
    evidence_obj = UncertaintyEvidence.build("eval-1", "evidence-1", units)
    spec = UncertaintySpecification("method-1", DependenceClass.SERIAL, "serial dependence is explicit", "v1")
    assert evidence_obj.attach_specification(spec).specification == spec


def test_a50_research_registry_preserves_candidate_population():
    registry = ResearchSelectionRegistry.build((candidate(),))
    assert registry.selection_population_size == 1
    assert registry.final_test_eligible()


def test_a51_final_holdout_rejects_prior_test_observation():
    with pytest.raises(ValueError):
        HoldoutCandidate("cand-1", "eval-1", "result-1", True, False)


def test_a53_promotion_requires_statistical_claim_eligibility():
    eligibility = assemble_promotion_eligibility(holdout(), stats())
    assert eligibility.eligible_for_policy_decision()


def test_a54_live_authorization_requires_approved_promotion_and_operational_evidence():
    eligibility = assemble_promotion_eligibility(holdout(), stats())
    decision = PromotionDecision("promo-1", "eval-1", "policy", "v1", "approved", "criteria satisfied")
    readiness = assemble_deployment_readiness(
        eligibility, decision,
        operational_evidence_id="ops-1",
        gate_policy_id="gate-1",
        gate_policy_version="v1",
        status=GateStatus.AUTHORIZED,
        live_authorization_id="live-1",
    )
    assert readiness.live_trading_authorized


def test_a55_operational_control_requires_matching_observation():
    observation = OperationalObservation("obs-1", "feed", 1000, HealthState.DEGRADED, "evidence-1")
    decision = OperationalControlDecision("decision-1", "obs-1", SafetyAction.BLOCK_NEW, "policy", "v1", "degraded")
    assert apply_operational_control(observation, decision) == decision


def test_a56_halted_state_cannot_generate_signals():
    with pytest.raises(ValueError):
        OperationalTradingState(
            "state-1", OperationalState.HALTED,
            TradingPermissions(True, False, True, True),
            "obs-1", "policy", "v1",
        )


def test_a57_resume_requires_recovered_state():
    recovery = RecoveryDecision("recovery-1", "halted", RecoveryState.RECOVERED, "obs-1", "evidence-1", "policy", "v1", 100)
    authorization = ResumeAuthorization("resume-1", "recovery-1", 100, "policy", "v1")
    assert authorize_resume(recovery, authorization) == authorization


def test_a58_audit_chain_is_temporally_ordered():
    record = DecisionAuditRecord("audit-1", 100, "decision-1", "policy", "v1", (AuditLink("prediction", "pred-1"),))
    chain = append_audit_record((), record)
    with pytest.raises(AuditChainError):
        append_audit_record(chain, DecisionAuditRecord("audit-2", 99, "decision-1", "policy", "v1", (AuditLink("prediction", "pred-1"),)))


def test_a59_execution_boundary_requires_authorization_and_fill_bounds():
    intent = OrderIntent("intent-1", "opp-1", "auth-1", "size-1", "NIFTY", "BUY", 10, "MARKET", 100, "2.1", "exec-1")
    lifecycle = authorize_order(intent, "auth-1")
    lifecycle = record_submission(lifecycle, 101, True)
    lifecycle = record_fill(intent, lifecycle, 10, 102)
    assert lifecycle.state.value == "filled"
    with pytest.raises(ExecutionBoundaryError):
        record_fill(intent, lifecycle, 1, 103)


def test_a60_complete_chain_requires_immediate_causal_parent():
    events = []
    for index, stage in enumerate(ChainStage):
        events.append(ChainEvent(stage, f"e{index}", index, None if index == 0 else f"e{index - 1}"))
    validate_causal_chain(tuple(events))
    events[5] = ChainEvent(events[5].stage, events[5].event_id, events[5].occurred_at_ms, "wrong")
    with pytest.raises(EndToEndGateError):
        validate_causal_chain(tuple(events))


def test_a60_order_intent_requires_authorization_stages():
    events = []
    for index, stage in enumerate(ChainStage):
        events.append(ChainEvent(stage, f"e{index}", index, None if index == 0 else f"e{index - 1}"))
    validate_no_execution_without_authorization(tuple(events))


def test_a61_accounting_effects_derive_from_confirmed_fill():
    fill = AccountingFill("fill-1", "intent-1", "NIFTY", 10, 100.0, 100)
    effect = derive_position_effect(fill, 10)
    accounting = derive_accounting_event(fill, effect)
    assert accounting.fill_id == fill.fill_id
    assert accounting.position_effect_id == effect.effect_id
