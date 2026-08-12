# Adaptive Edge V2 — Training / Validation / Test Walk-Forward Evaluation Contract

**Artifact:** A39
**Version:** 2.0.0-draft
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
**Implementation:** PARTIAL — temporal evaluation primitives implemented; numerical evaluation remains blocked

## 1. Purpose

A39 defines the statistical evaluation architecture required to determine whether Adaptive Edge has demonstrated an out-of-sample edge under temporal adaptation.

It does not declare profitability, statistical significance, or production readiness. It defines the conditions under which such claims may later be evaluated.

## 1A. Implementation status

The following architecture is now implemented in `backend/app/engines/adaptive_edge/walk_forward.py`:

```text
TemporalSpan
EvaluationCycle
EvaluationObservation
causal training eligibility
walk-forward sequence validation
explicit outcome-span purging
overlapping-outcome detection
independent-episode counting
CandidateSpec / CandidateResult
ResearchRegistry
FinalHoldout protection
final-test claim eligibility gate
```

The implementation is intentionally conservative:

```text
implemented
    = temporal/evaluation invariants

not implemented
    = target definition
    = outcome horizon
    = expanding vs rolling policy
    = purge duration
    = embargo duration
    = model/hyperparameter selection rule
    = statistical uncertainty estimator
    = promotion threshold
    = final performance metrics
```

No unresolved A26 target/horizon semantics are inferred by the implementation. A purge operation therefore requires an explicitly supplied resolved `outcome_span`; it does not invent a horizon. Test-set contamination is recorded explicitly and invalidates final-test evidence when test results influence selection.

## 2. Why walk-forward evaluation is required

Adaptive Edge is explicitly intended to evolve through versioned learning and promotion.

Therefore a single static train/test split is insufficient to represent the intended operating process.

The evaluation must preserve the temporal sequence:

```text
past information
    -> training
    -> validation/model selection
    -> promotion
    -> future evaluation
    -> later information
    -> next training cycle
```

## 3. Canonical walk-forward unit

Each evaluation cycle `k` is represented as:

```text
Cycle_k = {
    training_boundary
    validation_boundary
    test_boundary
    purge_boundary
    embargo_boundary
    feature_policy_version
    label_policy_version
    model/policy version
    promotion_time
}
```

Exact dates and window lengths are not selected by A39.

## 4. Causal ordering

For every cycle:

```text
Training information
    <
Validation information
    <
Promotion
    <
Test information
```

The exact ordering must account for label maturity and any feature availability lag.

A future test outcome cannot affect the model promoted before that test period.

## 5. Training population

Training may contain only observations that satisfy A38:

```text
label_maturity_time <= training_cutoff
feature_available_time <= decision_time
```

plus any required purge/embargo constraints.

## 6. Validation population

Validation is used for model/policy selection and tuning.

Therefore it is not an untouched estimate of final generalization after repeated research.

Once validation observations influence model selection, they are part of the research process.

## 7. Test population

The test set is reserved for evaluating a frozen candidate/policy selection process.

Once test results influence further parameter/model/policy selection, the test set is no longer an untouched test set.

The evaluation registry must record such use.

## 8. Walk-forward sequence

Conceptually:

```text
         TRAIN       VALIDATE       TEST
---------|-------------|--------------|-------->
         ^             ^              ^
      cutoff        selection      future
```

The process then advances:

```text
Cycle 1 -> Cycle 2 -> Cycle 3 -> ... -> Cycle N
```

with each cycle respecting causal ordering.

## 9. Expanding versus rolling training

A39 does not choose between:

```text
expanding window
rolling window
```

The choice is a strategy/policy parameter requiring validation.

The selected policy must be frozen before final evaluation.

## 10. Purging

If an observation's label horizon overlaps a validation/test boundary, the observation may contain future information relative to the boundary.

Such observations must be purged according to the later resolved horizon semantics.

Exact purge duration is UNKNOWN until A26 resolves the target horizon.

## 11. Embargo

If nearby observations remain statistically or informationally dependent after purging, an embargo may be required between train and evaluation boundaries.

A39 establishes the architectural need for embargo where justified but does not invent its duration.

## 12. Overlapping observations

High-frequency or repeated decisions can create overlapping outcome windows.

This violates the assumption that observations are automatically independent.

Evaluation must therefore distinguish:

```text
number of observations
number of independent economic episodes
```

The exact dependence model remains unresolved.

## 13. Multiple-testing control

The research process may evaluate:

```text
features
thresholds
horizons
models
hyperparameters
instrument policies
execution assumptions
```

and select the best result.

This creates research-selection bias.

A39 therefore requires the evaluation registry to preserve the tested candidate population, not only the winning configuration.

## 14. Research registry

Every candidate evaluated during research must be identifiable by:

```text
candidate_id
code/version
feature version
label version
parameter set
training boundary
validation boundary
execution assumptions
selection rationale
result metrics
```

Deleting unsuccessful candidates destroys auditability and can hide multiple-testing effects.

## 15. Hyperparameter tuning

Hyperparameters may be tuned using training/validation data.

They may not be tuned using the final untouched test set.

If the test set is inspected and used for tuning, it must be reclassified as research data and replaced by a new untouched evaluation boundary.

## 16. Model selection

The selected model/policy is a function of the research process:

```text
SelectedCandidate
    = SelectionFunction(AllEvaluatedCandidates, ResearchPolicy)
```

It is invalid to evaluate only the winner while ignoring how the winner was selected.

## 17. Test-set reuse

Repeated test evaluation creates implicit overfitting even if no explicit parameter is changed.

Therefore test-use history must be recorded.

A final claim of out-of-sample performance requires an untouched or appropriately reconstituted final evaluation population.

## 18. Adaptive promotion

A promoted model/policy can only affect decisions after its promotion boundary:

```text
active_from >= promotion_time
```

No future-trained model may be applied to earlier observations.

## 19. Historical replay

A full historical replay must reproduce the sequence:

```text
data available at t
-> model version active at t
-> prediction
-> decision
-> execution
-> outcome
```

It must not use the final model for the entire historical period unless the evaluation question explicitly concerns a non-adaptive fixed model.

## 20. Performance aggregation

Cycle-level results must be preserved before aggregation.

A single aggregate metric can hide:

```text
regime dependence
performance decay
cycle failure
parameter instability
```

Therefore the evaluation artifact must retain per-cycle metrics and observations.

## 21. Parameter stability

A candidate should not be considered robust solely because one parameterization performs well.

Sensitivity to nearby validated parameter choices must be evaluated without selecting favorable alternatives after observing the final test result.

No numerical sensitivity range is selected here.

## 22. Regime dependence

Performance may vary across market regimes.

A39 requires regime-conditioned evaluation where regime definitions are part of the canonical strategy specification.

No regime taxonomy is invented here.

## 23. Data-quality dependence

Evaluation must preserve data-quality failures and missingness rather than silently dropping difficult observations when that changes the effective sample.

The data-quality policy must record exclusions and their reasons.

## 24. Survivorship

The evaluation universe must reflect historical availability at each decision time.

Current surviving contracts cannot be substituted for the historical universe.

## 25. Selection bias in execution

If execution assumptions are tuned after seeing historical P&L, the evaluation is contaminated.

Execution model versions must therefore be included in the candidate/evaluation registry.

## 26. Look-ahead attack

The following are explicitly invalid:

```text
future label -> training before maturity
future test outcome -> parameter selection
future liquidity -> historical contract selection
future fill -> historical execution assumption
future volatility -> historical feature
```

## 27. Leakage through adaptive normalization

Any normalization/scaling/feature transformation learned from data must be fit within the training boundary of each cycle.

A global full-history transform is invalid for causal evaluation.

## 28. Leakage through feature selection

Feature selection must be performed within the research boundary.

A feature selected using future validation/test performance cannot be treated as if it had been known at the original training cutoff.

## 29. Leakage through target engineering

Any transformation that uses future outcome information is label construction, not feature construction.

It must remain outside the feature pipeline.

## 30. Statistical uncertainty

Performance estimates require uncertainty characterization.

A39 does not select a particular confidence interval, bootstrap, block-bootstrap, or other estimator.

The appropriate method depends on the dependence structure and outcome definition.

## 31. Non-independence

Standard IID statistical assumptions must not be applied automatically to overlapping financial observations.

The evaluation method must justify any independence assumption it uses.

## 32. Economic significance

Statistical significance alone is insufficient.

Evaluation must eventually examine:

```text
net economic result
execution costs
risk
drawdown
capacity/feasibility
stability
```

Exact metrics remain downstream artifacts.

## 33. Negative-result preservation

A production-grade research system must retain failed cycles and failed candidates.

Deleting them creates survivorship in the research process itself.

## 34. Final holdout

A final holdout may be maintained after all architecture, policy, feature, parameter, and execution assumptions are frozen.

The exact holdout boundary is unresolved until the historical dataset and A26 horizon are known.

## 35. Promotion gate

A candidate may be promoted only after satisfying the applicable pre-defined promotion policy.

No threshold is invented by A39.

The promotion rule itself must be versioned before it is used for final evaluation.

## 36. Reproducibility

A complete evaluation must be reproducible from:

```text
raw-data versions
canonical-data versions
feature version
label version
candidate version
execution model version
cycle boundaries
research registry
random seeds where applicable
code version
```

## 37. Parameter classes

### Frozen architecture

```text
walk-forward evaluation
causal temporal ordering
training/validation/test separation
purging/embargo capability
research registry
candidate preservation
cycle-level result preservation
final holdout protection
reproducibility
```

### Learned/configurable

```text
window lengths
purge duration
embargo duration
model hyperparameters
promotion thresholds
update frequency
```

These require proper validation and must not be chosen from final-test performance.

### External UNKNOWN

```text
historical dataset coverage
outcome horizon
execution data completeness
market-regime definition
provider correction history
```

## 38. Implementation gate

A39 may be implemented as an evaluation framework without numerical strategy assumptions.

A production evaluation implementation is blocked until A26 target/horizon and the relevant feature, execution, and accounting semantics are resolved.

## 39. Completion criterion

A39 becomes `RESOLVED` when the evaluation system can demonstrate for every evaluated decision:

```text
what data was available
which feature version was active
which label was mature
which candidate was active
which policy selected it
what execution assumptions were used
which boundary contained the observation
whether the observation was used in training/validation/test
```

and reproduce the result without future leakage.

## ARCHITECTURE STATUS

**FROZEN:** walk-forward architecture; causal ordering; train/validation/test separation; purge/embargo capability; research registry; candidate preservation; cycle-level results; final holdout protection; reproducibility.

**IMPLEMENTED PRIMITIVES:** temporal boundaries; A38 training eligibility; explicit outcome-span purge; overlap detection; candidate/result registry; final-holdout protection; test-contamination gate.

**UNRESOLVED:** expanding vs rolling window; purge/embargo durations; statistical uncertainty method; regime definitions; promotion thresholds; update frequency; exact performance metrics.

**BLOCKERS:** A26 target/horizon and several upstream source semantics remain unresolved. These block final numerical evaluation but not the evaluation architecture.

**NEXT ARTIFACT:** A40 — Feature Availability, Snapshot and Feature-Lineage Contract.
