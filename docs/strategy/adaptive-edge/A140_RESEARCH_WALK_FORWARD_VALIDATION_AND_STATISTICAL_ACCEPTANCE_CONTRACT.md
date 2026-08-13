# A140 — Canonical Research, Walk-Forward Validation & Statistical Acceptance Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH
**Version:** 1.0

## Purpose

Define how Adaptive Edge converts hypotheses into reproducible evidence without allowing the research process to contaminate the evidence that justifies the strategy.

```text
HYPOTHESIS
  -> EXPERIMENT
  -> DATA FREEZE
  -> WALK-FORWARD EVIDENCE
  -> STATISTICAL VALIDATION
  -> ECONOMIC VALIDATION
  -> EXECUTION VALIDATION
  -> ROBUSTNESS
  -> PROMOTION / REJECTION
```

## 1. Experiment identity

Every experiment records an immutable `experiment_id` and references:

```text
parent_experiment_id
hypothesis
dataset_version
feature_version
label_version
formula_version
configuration_version
model_version
parameter_search_space
evaluation_protocol
execution_model_version
randomization/seeds where applicable
```

Changing an evidence-producing component creates a new experiment.

## 2. Chronological boundaries

```text
DEVELOPMENT < VALIDATION < TEST < FINAL_HOLDOUT
```

No future period may influence an earlier period's feature, preprocessing, parameter, threshold, calibration, model, or selection.

## 3. Walk-forward protocol

```text
TRAIN -> CALIBRATE -> VALIDATE -> FREEZE -> FORWARD_TEST -> ADVANCE
```

Scheduled adaptation is permitted only where its trigger and cadence were predefined and validated before being used as evidence.

## 4. Multiple-testing registry

Every tested candidate and parameter configuration is recorded, including failures. The research ledger records the search breadth so the winning result is interpreted in light of selection effects.

```text
best_of_many != single_predeclared_test
```

## 5. Baseline and ablation

Every major improvement requires a versioned baseline and, where applicable:

```text
FULL
FULL - X
```

to determine incremental contribution. Interaction effects are tested separately where components may depend on one another.

## 6. Statistical and economic separation

Promotion requires independent evidence across applicable gates:

```text
STATISTICAL
ECONOMIC
RISK
EXECUTION
ROBUSTNESS
```

A statistically detectable effect is not automatically economically useful. Historical profitability alone is not sufficient evidence.

## 7. Execution realism

Research must account for the canonical execution model where relevant. Unknown costs, fills, liquidity, spread, fees, taxes, or broker semantics must remain `UNKNOWN` rather than silently becoming zero or perfect execution.

## 8. Parameter stability

Selected parameters must be evaluated against nearby values and, where appropriate, across regimes and walk-forward windows. Broad stable regions are preferred to isolated optima.

No numerical parameter is frozen by this artifact.

## 9. Leakage audit

Before promotion, audit:

```text
timestamps
dependency availability
future values
aggregation boundaries
label contamination
universe membership
preprocessing
normalization
calibration
model selection
```

Any material unresolved leakage blocks promotion.

## 10. Selection and survivorship bias

Research populations must be defined at the historical decision time. Current surviving instruments or executed trades must not be substituted for the historical opportunity population without an explicit, justified sampling design.

## 11. Label and overlap controls

Each label records its start, end, positive/negative/unknown conditions, and maturity. Overlapping observations require explicit dependence handling, including purge/embargo rules where applicable.

## 12. Search discipline

The parameter/search space is declared before confirmatory execution. Expanding the search after observing results creates a new experiment or remains exploratory; it cannot silently become confirmatory evidence.

## 13. Robustness

Applicable robustness tests include:

```text
parameter perturbation
regime segmentation
time-window perturbation
execution-cost perturbation
liquidity perturbation
feature ablation
model simplification
null/randomization tests appropriate to temporal dependence
```

The exact test set is configuration, not a universal fixed list.

## 14. Null and randomization tests

Where used, null construction must preserve relevant temporal dependence and market structure. Naive shuffling is forbidden when it destroys dependencies essential to the hypothesis.

## 15. Research stop rule

Research must transition explicitly from exploratory to confirmatory work. Endless experimentation after observing results is not valid confirmation.

## 16. Promotion state machine

```text
RESEARCH_ONLY
      |
      v
VALIDATED_CANDIDATE
      |
      v
FORWARD_TESTED
      |
      v
FINAL_HOLDOUT
     /    \
    v      v
REJECTED  PRODUCTION_CANDIDATE
```

A critical failure at any stage produces `REJECTED`.

## 17. Final holdout

Once development is declared complete, the final holdout is executed under the frozen protocol. After inspection, it is no longer an untouched holdout.

If it fails, the candidate is rejected. A modified strategy starts a new research cycle; the same holdout cannot be repeatedly consumed while retaining its untouched status.

## 18. Reproducibility

A result must be reproducible from immutable versions of:

```text
data
features
labels
formulas
configuration
model
execution model
experiment definition
randomization seeds where applicable
```

If a dependency is nondeterministic or externally changing, the dependency and limitation are recorded explicitly.

## 19. Statistical acceptance boundary

This artifact deliberately does not invent universal values for:

```text
p-value
confidence level
minimum sample size
Sharpe threshold
maximum drawdown
minimum expectancy
minimum win rate
```

Those are policy/validation parameters and must be justified for the specific hypothesis and population. Statistical significance alone cannot override risk or execution failure.

## 20. Failure conditions

Promotion is blocked by:

```text
material leakage
unresolved causal violation
invalid dataset boundary
untracked search expansion
survivorship/selection bias that invalidates the claim
unrealistic execution assumptions
critical risk invariant failure
absence of out-of-sample evidence
material parameter fragility
non-reproducible result
final-holdout failure
```

## 21. Audit lineage

```text
experiment
 -> dataset
 -> snapshot/features
 -> model/parameters
 -> decision
 -> outcome/label
 -> evaluation
 -> acceptance decision
 -> promoted model/policy version
```

Failed experiments remain immutable research history.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- experiment identity
- chronological research boundaries
- walk-forward protocol
- candidate/search registry
- multiple-testing accounting
- baseline preservation
- ablation/incremental-value testing
- leakage auditing
- selection/survivorship controls
- robustness framework
- statistical/economic separation
- final-holdout protection
- promotion/rejection state machine
- reproducibility and lineage

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- concrete external dataset coverage
- concrete statistical library/implementation
- concrete model/dataset registry technology

CONFIGURATION TO VALIDATE:
- purge/embargo intervals
- search budgets
- robustness perturbation sets
- promotion gates
- paper/shadow/live gates

LEARNED / VALIDATION-DEPENDENT:
- numerical acceptance thresholds
- label thresholds/horizons
- model family and hyperparameters
- calibration method
- adaptation cadence

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A141 — Canonical Model/Policy Registry, Version Authority & Promotion/Rollback Contract
```
