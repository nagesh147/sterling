# A47 — Out-of-Sample Evaluation Result / Claim Protection Contract

**Version:** 2.0.0-draft  
**Artifact:** A47  
**Status:** FRAMEWORK IMPLEMENTED  
**Depends on:** A39, A40, A41, A42, A43, A44, A45, A46

## 1. Purpose

A47 defines when an evaluation result may support an untouched out-of-sample claim and when later research use invalidates that claim.

A47 does not define profitability, statistical significance, confidence intervals, promotion thresholds, target horizons, or economic performance metrics.

## 2. Evidence identity

An evaluation result must preserve:

```text
 evaluation identity
 candidate identity
 code version
 feature version
 label version
 execution version
 evaluation boundary
 result fingerprint
```

The result must remain attributable to the exact research configuration that produced it.

## 3. Untouched claim

An evaluation is claim-eligible only when its recorded test-use history contains no event showing that its test result was inspected or used in subsequent research selection.

Conceptually:

```text
No test-use contamination
        |
        v
Claim eligible
```

Eligibility is a lineage property, not a statement that the strategy is profitable or statistically significant.

## 4. Test contamination

A test result becomes contaminated when it is used to influence research decisions, including candidate selection, parameter selection, model selection, policy selection, or execution-assumption selection.

Repeated inspection that affects subsequent research is also research use.

```text
Test result
    |
    +--> influences research
    |
    v
CONTAMINATED
```

The contamination event must remain recorded.

## 5. Reconstitution

Once a final holdout is contaminated, it cannot be restored to untouched status merely by ignoring the result thereafter.

A new evaluation boundary is required.

```text
Contaminated holdout
        |
        v
New frozen research state
        |
        v
Replacement holdout
        |
        v
Potentially eligible claim
```

A47 records this as `RECONSTITUTED`; it does not assert that the replacement boundary is automatically statistically valid.

## 6. Candidate-selection preservation

A claim must remain connected to the candidate-selection process that produced the evaluated candidate.

A winning candidate cannot be presented as though it had been specified before research if it was selected after inspecting the evaluation result.

A39's research registry remains the authority for the full candidate population.

## 7. Metrics

A47 stores metric identities only. It does not choose metric definitions or thresholds.

The following remain external contracts:

```text
net return
risk
maximum drawdown
statistical uncertainty
economic significance
capacity
execution quality
```

No numerical threshold is invented by A47.

## 8. Historical replay relationship

A46 establishes deterministic reconstruction. A47 establishes whether the reconstructed evaluation can support an out-of-sample claim.

```text
A46
historical reconstruction
        |
        v
A39
walk-forward evaluation
        |
        v
A47
claim protection
```

## 9. Required lineage

A claim is not eligible for a strong out-of-sample statement when required lineage is missing, including the identity of the evaluated candidate, code, feature, label, execution assumptions, evaluation boundary, or result fingerprint.

The implementation must fail closed rather than infer missing provenance.

## 10. Explicit non-goals

A47 does not define:

- target or horizon semantics;
- model architecture;
- hyperparameter values;
- statistical estimator;
- significance threshold;
- profitability threshold;
- promotion rule;
- execution cost assumptions;
- option selection;
- risk allocation; or
- production readiness.

## 11. Completion criterion

A47 is structurally complete when the system can determine, for an evaluation result:

```text
what candidate was evaluated
what exact versions produced it
what evaluation boundary was used
whether test results were subsequently used
which contamination events exist
whether a replacement holdout is required
```

without silently converting a contaminated result into an untouched out-of-sample claim.

## 12. Architecture status

**FROZEN:** evidence identity, test-use recording, contamination invalidation, replacement-boundary requirement, fail-closed lineage.

**IMPLEMENTED:** evaluation evidence, test-use events, claim-status assessment, contaminated-claim detection, replacement-holdout representation.

**UNRESOLVED:** statistical uncertainty method, promotion threshold, economic significance criteria, target/horizon semantics, and final performance metrics.
