# Adaptive Edge V2 — Economic Value, Expected Value and Decision Utility Contract

**Artifact:** A42  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** INTERFACE-ONLY

A42 defines the causal boundary between prediction and an economically meaningful decision.

```text
Prediction
    |
    +--> Outcome/payoff definition
    +--> Execution economics
    +--> Risk constraints
    |
    v
Expected Economic Value
    |
    v
Decision Utility / Eligibility
    |
    v
Decision
```

A probability or score alone does not determine whether an action is economically justified. The economic layer requires an explicitly defined mapping from possible outcomes to economic consequences.

The structural expected-value relationship is:

```text
E[G | X] = Σ_y P(Y=y | X) * G(y)
```

for a discrete outcome space, with the corresponding expectation/integral for continuous outcomes. This is only the mathematical structure; it does not define the actual target, payoff, probability semantics, or distribution.

If execution cost `C` is defined, the structural net relationship is:

```text
NetValue = GrossValue - C
```

The cost must be an ex-ante quantity available at decision time. A future realized cost cannot be retrospectively substituted into the decision.

A42 requires an explicit risk constraint:

```text
RiskMeasure(action, state) <= RiskLimit
```

and an explicit no-action baseline. Expected monetary value and utility are not assumed to be identical.

The information set must satisfy A40/A41 causality. Future observations, future model state, future costs, future favorable excursion, or realized future outcomes cannot enter the pre-trade calculation.

Every decision must preserve provenance:

```text
decision_id
prediction_id
feature_snapshot_id
economic_assessment_id
risk_assessment_id
execution_assessment_id
policy_version
decision_time
reason/status
```

No-action results must distinguish explicit failure reasons such as:

```text
PREDICTION_INVALID
ECONOMIC_VALUE_INSUFFICIENT
RISK_CONSTRAINT
EXECUTION_CONSTRAINT
CONTRACT_CONSTRAINT
DATA_INVALID
POLICY_DISABLED
OTHER_EXPLICIT_FAILURE
```

Missing economics must fail closed or enter an explicitly defined degraded state. It must not silently become zero cost, zero risk, average payoff, default probability, or a future value.

## Implementation gate

A42 does not authorize a new numerical expected-value, utility, threshold, payoff, execution-cost, or risk formula. The structural decision interface may be implemented independently.

## Status

**FROZEN:** prediction/economics separation; causal information set; explicit action set; no-action baseline requirement; cost/risk separation; decision provenance; explicit rejection reasons; fail-closed missing economics.

**UNRESOLVED:** payoff function; outcome distribution; expected-cost model; utility function; minimum edge; decision threshold; opportunity cost; risk adjustment; instrument economic conversion.

**BLOCKERS:** A26 target/outcome semantics; A32 risk semantics; A35 execution-cost semantics; A37 accounting/instrument semantics; A41 probability semantics.

**NEXT ARTIFACT:** A43 — Decision / Eligibility / Risk-Authorization State Machine.
