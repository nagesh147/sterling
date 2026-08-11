# CANONICAL RESEARCH EXPERIMENT AND VERSION-CONTROL SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how strategy research is conducted, recorded, reproduced, compared, rejected, and promoted.

The objective is to prevent:

```text
uncontrolled experimentation
data leakage
selection bias
p-hacking
multiple-testing contamination
parameter provenance loss
silent model mutation
irreproducible results
```

The research process itself becomes a controlled system.

---

# 2. Fundamental Principle

No research result is considered valid merely because:

```text
the code ran
the backtest made money
the chart looked good
```

A valid result requires:

```text
defined hypothesis
+
defined dataset
+
defined model version
+
defined parameters
+
defined evaluation protocol
+
reproducible execution
+
recorded result.
```

---

# 3. Research Lifecycle

The canonical lifecycle is:

```text
IDEA
  ↓
HYPOTHESIS
  ↓
EXPERIMENT DEFINITION
  ↓
DATA SNAPSHOT
  ↓
CANDIDATE BUILD
  ↓
VALIDATION
  ↓
RESULT
  ↓
ANALYSIS
  ↓
ACCEPT / REJECT / MODIFY
```

If modified:

```text
NEW EXPERIMENT
```

not:

```text overwrite old experiment.
```

---

# 4. Experiment Identity

Every experiment receives:

```text
ExperimentID
```

The identifier is immutable.

Example:

```text
EXP-2026-000001
```

The exact identifier format remains an implementation detail.

---

# 5. Experiment Definition

Every experiment must define:

```text
ExperimentID
Hypothesis
ResearchQuestion
ParentExperimentID
ModelVersion
DatasetVersion
ParameterVersion
ExecutionModelVersion
RiskPolicyVersion
AccountingVersion
CreatedAt
Researcher
Status
```

---

# 6. Hypothesis

Every experiment must begin with an explicit hypothesis.

Example:

```text
HYP-001

A fifteen-minute opening-range breakout,
conditioned on validated market-state variables,
produces positive net option expectancy after realistic execution costs.
```

The hypothesis must be stated before evaluating the result.

---

# 7. Hypothesis Type

Each hypothesis receives a classification:

```text
PREDICTIVE
ECONOMIC
EXECUTION
RISK
MANAGEMENT
DATA
ARCHITECTURAL
```

This prevents unrelated improvements from being evaluated as though they tested the same claim.

---

# 8. Hypothesis Null

Where statistically meaningful, the experiment defines:

```text H0
```

and:

```text H1
```

For example:

```text H0:
The candidate provides no incremental net economic value.

H1:
The candidate provides positive incremental net economic value.
```

---

# 9. Research Question

The experiment must answer one primary question.

For example:

```text Does adding volatility state improve out-of-sample expectancy?
```

Not:

```text Does this strategy work?
```

The latter is too broad.

---

# 10. Primary Metric

Every experiment defines a primary evaluation metric before results are inspected.

Examples:

```text Net expectancy
Calibration error
Execution cost
Maximum drawdown
```

The primary metric must correspond to the hypothesis.

---

# 11. Secondary Metrics

Secondary metrics may include:

```text Net P&L
Win rate
Profit factor
Drawdown
Sharpe-like statistics
Execution cost
Trade frequency
Calibration
```

Secondary metrics cannot silently replace the primary metric after observing results.

---

# 12. Dataset Identity

Every experiment references an immutable:

```text DatasetVersion.
```

The dataset version records:

```text source
coverage
timestamp semantics
instrument universe
data transformations
missing-data treatment
adjustments
schema version
creation timestamp.
```

---

# 13. Dataset Snapshot

An experiment must use a reproducible dataset snapshot.

Conceptually:

```text DatasetSnapshot
=
Source
+
Coverage
+
Transformations
+
Version
+
Checksum.
```

The exact storage mechanism is implementation-dependent.

---

# 14. No Mutable Dataset Dependency

A historical experiment cannot depend on:

```text "whatever data currently exists."
```

The dataset must be versioned.

If the data changes:

```text New DatasetVersion.
```

---

# 15. Parameter Registry

Every parameter used by an experiment must have:

```text ParameterID
ParameterName
Value
Unit
Type
Source
Status
Version
```

---

# 16. Parameter Provenance

Each parameter must identify whether it is:

```text FIXED
LEARNED
CALIBRATED
EXTERNAL
RESEARCH
DERIVED
```

A numerical value without provenance is invalid research metadata.

---

# 17. Parameter Change

Changing any materially relevant parameter creates:

```text New ParameterVersion.
```

The previous value remains preserved.

---

# 18. Architecture Change

Changing:

```text state definition
feature definition
label definition
transition rule
economic formula
risk formula
execution semantics
```

creates a new:

```text ModelVersion.
```

It is not merely a parameter update.

---

# 19. Parent Experiment

Every modified experiment may reference:

```text ParentExperimentID.
```

This creates an explicit research lineage:

```text EXP-001
   ↓
EXP-002
   ↓
EXP-003
```

---

# 20. Research Tree

The complete research history forms a directed acyclic graph:

```text Experiment
      ↓
Candidate
      ↓
Experiment
      ↓
Candidate
```

Circular research lineage is prohibited.

---

# 21. Why the Research Graph Matters

Without lineage, it becomes impossible to determine:

```text how many ideas were tested
which model was selected
which parameters were changed
which failures were discarded
```

That creates severe selection bias.

---

# 22. Experiment Status

An experiment may have:

```text DRAFT
REGISTERED
RUNNING
COMPLETED
ANALYZED
ACCEPTED
REJECTED
SUPERSEDED
INVALIDATED
```

A completed experiment cannot silently revert to draft.

---

# 23. Registered Experiment

Once an experiment is:

```text REGISTERED
```

the primary hypothesis and evaluation protocol are frozen.

Material changes require a new experiment.

---

# 24. Exploratory Research

Exploration is permitted before registration.

However:

```text exploratory results
```

are explicitly classified as:

```text EXPLORATORY EVIDENCE.
```

They cannot be presented as confirmatory evidence.

---

# 25. Confirmatory Research

A registered experiment becomes:

```text CONFIRMATORY
```

only after:

```text hypothesis
dataset
evaluation protocol
primary metric
```

have been frozen.

---

# 26. Experiment Configuration

The experiment configuration must capture:

```text model version
parameter version
dataset version
walk-forward configuration
execution configuration
risk configuration
accounting configuration
random seeds where applicable.
```

---

# 27. Randomness

If an experiment contains randomness:

```text random seed
```

must be recorded.

If multiple seeds are used:

```text all seeds
```

must be recorded.

---

# 28. Determinism

For deterministic components:

```text same inputs
+
same versions
=
same outputs.
```

For stochastic components:

```text same inputs
+
same versions
+
same seed
=
same reproducible run.
```

---

# 29. Run Identity

Each actual execution of an experiment receives:

```text RunID.
```

Example:

```text RUN-2026-000041
```

An experiment may have multiple runs.

---

# 30. Run Environment

The run records:

```text software version
code commit
configuration
dataset version
runtime environment
dependency versions
```

where technically applicable.

---

# 31. Code Version

The exact implementation used for a run must be identifiable by:

```text immutable code revision / commit ID.
```

A result without code provenance is not fully reproducible.

---

# 32. Walk-Forward Run

A walk-forward experiment records every fold:

```text FoldID
TrainingPeriod
ValidationPeriod
TestPeriod
ParameterVersion
Result
```

---

# 33. Fold Independence

A test fold cannot influence parameter estimation for itself.

The experiment runner must enforce:

```text Test_t
```

is inaccessible to:

```text Fit_t
```

and:

```text Calibration_t
```

where applicable.

---

# 34. Fold Result

Each fold records:

```text NetPnL
GrossPnL
TradeCount
Expectancy
Drawdown
ExecutionCost
CalibrationMetrics
RiskMetrics
```

and any experiment-specific metrics.

---

# 35. Aggregate Result

The experiment may calculate aggregate metrics across folds.

But:

```text AggregateResult
```

does not replace:

```text IndividualFoldResults.
```

---

# 36. Fold Weighting

The aggregation method must be predetermined.

Examples:

```text equal-fold weighting
trade-weighted
time-weighted
```

Changing the aggregation method after observing results creates a new experiment.

---

# 37. Baseline

Every experiment should identify an appropriate baseline.

Examples:

```text ExistingStrategy
SimpleBreakout
UnconditionalDirection
NoSignal
```

The baseline must be evaluated under comparable:

```text data
cost
risk
execution
accounting
```

conditions.

---

# 38. Incremental Experiment

If testing component `X`:

```text Baseline
vs
Baseline + X
```

is preferred.

This isolates the contribution of `X`.

---

# 39. Ablation

Ablation experiments remove one component from the full model:

```text FullModel
vs
FullModel - X.
```

This determines whether `X` contributes measurable value.

---

# 40. Component Contribution

A component is justified only if it demonstrates:

```text robust incremental value
```

rather than:

```text isolated in-sample improvement.
```

---

# 41. Hyperparameter Search

Hyperparameter searches are explicitly recorded.

For example:

```text θ ∈ {θ1, θ2, θ3, ...}
```

Every materially evaluated candidate must be counted.

The winning parameter cannot be treated as though it was selected a priori.

---

# 42. Search Budget

Where feasible, each experiment records:

```text NumberOfCandidatesEvaluated.
```

This provides a measure of:

```text researcher degrees of freedom.
```

---

# 43. Multiple-Testing Ledger

The research system maintains:

```text CandidateID
Hypothesis
ParameterSet
Dataset
PrimaryMetric
Result
Status
```

for materially evaluated candidates.

---

# 44. Selection Bias

If:

```text one hundred candidates
```

are tested and:

```text one performs exceptionally,
```

that result is weaker evidence than if:

```text one candidate
```

was specified in advance.

The validation framework must account for this distinction.

---

# 45. Multiple-Testing Adjustment

Where formal statistical inference is used, appropriate methods may include:

```text Bonferroni
Holm
False Discovery Rate
Permutation-based procedures
```

The exact method depends on the research question.

No particular correction is mandated universally.

---

# 46. Backtest Selection Bias

The research system must explicitly distinguish:

```text performance discovered through search
```

from:

```text performance confirmed out-of-sample.
```

This distinction must survive into the final research report.

---

# 47. No Result-Based Experiment Renaming

An experiment cannot be renamed after results to make the original hypothesis appear more predictive.

The original hypothesis remains immutable.

---

# 48. No Result-Based Parameter Reclassification

A parameter cannot be retroactively declared:

```text "fixed"
```

after being optimized.

Its actual provenance must be recorded.

---

# 49. Research Notes

Researchers may record qualitative observations:

```text unusual market behavior
data anomalies
hypotheses for future testing.
```

These notes must not modify historical experiment results.

---

# 50. Result Record

Every completed run produces:

```text ResultRecord {
    RunID
    ExperimentID
    ModelVersion
    DatasetVersion
    ParameterVersion

    PrimaryMetric
    SecondaryMetrics

    FoldResults
    AggregateResults

    FailureStates
    Warnings

    ExecutionSummary
    RiskSummary
}
```

---

# 51. Failure Recording

Failures are first-class outputs.

Examples:

```text DATA_FAILURE
LEAKAGE_FAILURE
EXECUTION_FAILURE
RISK_FAILURE
INSUFFICIENT_SAMPLE
STATE_MACHINE_FAILURE
ACCOUNTING_FAILURE
```

The system must not convert failures into missing results.

---

# 52. Missing Result Versus Zero Result

These are different.

```text No run completed
```

is not:

```text P&L = 0.
```

The result schema must distinguish them.

---

# 53. Research Rejection

A candidate may be rejected because:

```text no predictive value
no economic value
poor calibration
execution sensitivity
risk instability
parameter fragility
regime dependence
insufficient evidence.
```

The rejection reason is recorded.

---

# 54. Research Acceptance

Acceptance means:

```text candidate merits progression to the next validation stage.
```

It does not automatically mean:

```text production-ready.
```

---

# 55. Superseded Candidate

A candidate may be superseded by a newer candidate.

The old candidate remains immutable.

Example:

```text Model v1.0
   ↓ superseded
Model v1.1
```

---

# 56. Invalidated Result

A result can later be marked:

```text INVALIDATED
```

if a methodological defect is discovered.

Examples:

```text future leakage
incorrect cost accounting
bad timestamp handling
incorrect option contract mapping.
```

The original result is not deleted.

---

# 57. Invalidation Lineage

An invalidated result must contain:

```text InvalidationReason
DetectedAt
DetectedBy
AffectedExperiments
CorrectiveAction
```

---

# 58. No Silent Corrections

If an implementation bug is discovered:

```text old result remains.
```

A corrected run produces:

```text new RunID
```

with the corrected code version.

---

# 59. Reproducibility Test

Important experiments should be replayable from:

```text DatasetVersion
+
ModelVersion
+
ParameterVersion
+
CodeVersion
+
Configuration
```

and produce equivalent results.

---

# 60. Research Artifact Bundle

A completed experiment should produce:

```text ExperimentDefinition
DatasetReference
CodeReference
Configuration
ParameterRegistry
RunMetadata
FoldResults
AggregateResults
Diagnostics
ValidationReport
```

---

# 61. Experiment Checksum

Where practical, the experiment configuration can have a deterministic identity derived from:

```text dataset
model
parameters
execution
risk
accounting
configuration.
```

This prevents accidental configuration drift.

---

# 62. Configuration Immutability

Once a run begins:

```text configuration is immutable.
```

Changing it produces:

```text new RunID.
```

---

# 63. Research Environment

The environment should distinguish:

```text exploratory environment
validation environment
production environment.
```

Production configuration cannot be modified through exploratory experimentation.

---

# 64. Production Model Registry

A separate model registry tracks:

```text ModelVersion
Status
PromotionDate
RiskPolicyVersion
ExecutionPolicyVersion
KnownLimitations
RetirementDate.
```

---

# 65. Model Promotion

Promotion requires an explicit transition:

```text VALIDATED
    ↓
PAPER_APPROVED
    ↓
LIVE_APPROVED
    ↓
PRODUCTION.
```

No implicit promotion is allowed.

---

# 66. Model Retirement

A model can be retired because of:

```text performance degradation
data changes
market-structure changes
execution deterioration
risk violation
replacement by superior validated model.
```

Retirement is recorded permanently.

---

# 67. Model Rollback

If production failure occurs:

```text current model
        ↓
approved previous model
```

may be restored only if the previous model is still valid under the current:

```text data contract
execution environment
risk policy.
```

---

# 68. Research-to-Production Boundary

The production system must consume only:

```text approved ModelVersion
approved ParameterVersion
approved RiskPolicyVersion
approved ExecutionModelVersion.
```

Research artifacts cannot directly enter production.

---

# 69. No Live Learning

The baseline production system does not permit:

```text trade outcome
        ↓
immediate parameter update
        ↓
next trade
```

because this creates an online feedback loop that requires a separate validated methodology.

---

# 70. Delayed Learning

If online/periodic learning is introduced later:

```text outcome maturity
        ↓
data eligibility
        ↓
training
        ↓
validation
        ↓
promotion
```

must occur before the updated model becomes active.

---

# 71. Experiment Separation

Different research questions must have different experiments.

For example:

```text EXP-A:
Does volatility state improve prediction?

EXP-B:
Does volatility state improve option selection?

EXP-C:
Does volatility state improve risk management?
```

These cannot be conflated.

---

# 72. Causal Interpretation

An observed improvement does not automatically establish causality.

For example:

```text Model + Feature X performs better.
```

The correct conclusion is:

```text evidence of incremental predictive/economic association.
```

Causal claims require stronger experimental design.

---

# 73. Experiment Scope

Each experiment must specify its scope:

```text prediction
option selection
execution
risk
management
```

This prevents a single experiment from silently changing several architectural layers.

---

# 74. Research Budget

The research process may eventually define limits on:

```text candidate count
hyperparameter evaluations
feature combinations
model families.
```

The exact budgets remain unfrozen.

The objective is to make researcher degrees of freedom measurable.

---

# 75. Pre-Registration Level

Not every exploratory experiment requires formal pre-registration.

However, any candidate intended for:

```text confirmatory evidence
final holdout
promotion
```

must be frozen before evaluation.

---

# 76. Research Integrity State

The research system may classify evidence as:

```text EXPLORATORY
CONFIRMATORY
VALIDATED
PRODUCTION.
```

These states must never be conflated.

---

# 77. Evidence Strength

A useful conceptual hierarchy is:

```text In-sample observation
        ↓
Out-of-sample observation
        ↓
Walk-forward evidence
        ↓
Adversarial robustness
        ↓
Paper trading evidence
        ↓
Controlled live evidence.
```

Evidence becomes stronger as uncontrolled assumptions decrease.

---

# 78. Research Report

Every serious candidate produces a standardized report containing:

```text Hypothesis
Methodology
Data
Parameters
Walk-forward design
Baselines
Ablations
Results
Failure analysis
Execution analysis
Risk analysis
Multiple-testing context
Limitations
Final disposition.
```

---

# 79. Limitations Are Mandatory

Every validation report must contain:

```text KnownLimitations.
```

Examples:

```text insufficient historical option depth
limited tick history
execution model uncertainty
small sample
regime coverage limitations.
```

A model is not considered more credible merely because its limitations are omitted.

---

# 80. Research Invariants

```text RES-001 id="8z2f3q"
Every material experiment has a unique identity.

RES-002
Every experiment references immutable data and model versions.

RES-003
Material parameter changes create new parameter versions.

RES-004
Material architecture changes create new model versions.

RES-005
Registered hypotheses cannot be silently rewritten.

RES-006
Exploratory evidence is not presented as confirmatory evidence.

RES-007
Final holdout results cannot determine parameter selection.

RES-008
Every materially evaluated candidate is recorded.

RES-009
Rejected candidates are preserved.

RES-010
Invalidated results are preserved with invalidation metadata.

RES-011
A run is reproducible from its versioned inputs.

RES-012
Experiment configuration is immutable during execution.

RES-013
Expected and realized results remain distinct.

RES-014
Research cannot directly mutate production state.

RES-015
Production models are versioned and immutable.

RES-016
Live learning is prohibited unless separately validated.

RES-017
Multiple-testing exposure is recorded.

RES-018
Ablation and baseline comparisons use compatible evaluation conditions.

RES-019
Failure is an explicit research result.

RES-020
Research lineage forms an auditable DAG.
```

---

# 81. Numerical Controls Still Unfrozen

We deliberately have not selected:

```text maximum experiment count
hyperparameter search budget
multiple-testing correction methodology
minimum evidence threshold
minimum number of independent experiments
minimum number of walk-forward folds
reproducibility tolerance
research expiration period
model retraining cadence.
```

These are process parameters to be established before formal research begins.

---

# 82. Canonical Research Chain

The entire research system is now:

```text
Hypothesis
    ↓
Experiment
    ↓
Versioned Dataset
    ↓
Versioned Model
    ↓
Versioned Parameters
    ↓
Walk-Forward Evaluation
    ↓
Execution Simulation
    ↓
Risk Evaluation
    ↓
Performance Attribution
    ↓
Adversarial Testing
    ↓
Validation
    ↓
Promotion / Rejection
```

Nothing important is allowed to bypass this chain.

---

# 83. Architecture Status

```text
Mathematical Specification              COMPLETE
Canonical Variable Registry             COMPLETE
Dependency Graph                         COMPLETE
State Transition Specification           COMPLETE
Historical Label Specification           COMPLETE
Statistical Estimation                  COMPLETE
Economic Decision                       COMPLETE
Option Selection                        COMPLETE
Risk Budget                             COMPLETE
Position Sizing                         COMPLETE
Execution / Slippage                    COMPLETE
P&L / Accounting                        COMPLETE
Performance Attribution                 COMPLETE
Model Validation                        COMPLETE
Promotion / Rejection                   COMPLETE
Research Experiment Control              COMPLETE
Version Control                          COMPLETE
```

The system now has both:

```text
TRADING SPECIFICATION
```

and:

```text
RESEARCH GOVERNANCE SPECIFICATION.
```

---

# 84. Next Artifact

The next logical artifact is the:

# CANONICAL SYNTHETIC MARKET AND ADVERSARIAL TEST SPECIFICATION

We already performed conceptual adversarial attacks earlier. Now we formalize them into a reusable test system.

It will define synthetic scenarios such as:

```text
steady trend
false breakout
whipsaw
volatility expansion
volatility collapse
gap
liquidity collapse
spread explosion
stale data
missing ticks
duplicate ticks
out-of-order events
rapid reversal
option premium distortion
extreme slippage
partial fills
risk-state corruption
```

For each scenario we will specify:

```text initial state
event sequence
expected state transitions
mathematical invariants
expected decision
expected risk behavior
expected accounting result
expected failure mode
```

That becomes our **formal verification test suite before implementation**, which is exactly where we should go next.