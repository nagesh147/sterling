# CANONICAL RESEARCH EXPERIMENT AND VALIDATION PROTOCOL

Version 1.0

## 1. Purpose

This specification defines the rules governing all future research performed on the strategy.

The central principle is:

```text
RESEARCH MUST NOT CHANGE THE EVIDENCE THAT JUSTIFIES THE RESEARCH.
```

Every experiment must therefore have:

```text
known inputs
known dataset boundaries
known hypothesis
known parameter space
known evaluation procedure
known decision rule
```

before results are inspected.

---

# 2. Research Is a Controlled Process

The research system is itself treated as a state machine.

```text
HYPOTHESIS
    |
    v
EXPERIMENT DESIGN
    |
    v
DATA FREEZE
    |
    v
EXECUTION
    |
    v
RESULTS
    |
    v
ANALYSIS
    |
    v
DECISION
```

The experiment cannot be redesigned after observing its results and still be called the same experiment.

---

# 3. Experiment Identity

Every experiment receives:

```text
ExperimentID
```

The identifier is immutable.

It references:

```text hypothesis
dataset version
code/model version
feature version
label version
parameter search space
evaluation protocol
random seeds where applicable
execution model version
```

---

# 4. Research Hypothesis

Every experiment must begin with an explicit hypothesis.

For example:

```text HYPOTHESIS-001
Adding calibrated opening-range momentum
improves out-of-sample directional discrimination
without materially increasing execution sensitivity.
```

This is superior to:

```text "Let's see whether this feature improves profit."
```

The latter encourages post-hoc interpretation.

---

# 5. Hypothesis Types

Experiments are classified as:

```text PREDICTION
ECONOMIC
EXECUTION
RISK
MANAGEMENT
MODE
DATA
ROBUSTNESS
```

This tells us what the experiment is actually testing.

---

# 6. Primary Metric

Before execution, every experiment must define a primary metric.

Examples:

```text prediction calibration
out-of-sample expectancy
net P&L
maximum drawdown
risk-adjusted return
execution-adjusted edge
```

The primary metric cannot be changed after seeing the results.

---

# 7. Secondary Metrics

Secondary metrics may include:

```text win rate
average win
average loss
MFE
MAE
holding time
turnover
slippage
drawdown duration
```

They provide context.

They cannot silently replace the primary metric.

---

# 8. Dataset Version

Every experiment references a specific:

```text DatasetVersion.
```

The dataset definition includes:

```text source
date range
instruments
fields
timestamp semantics
cleaning rules
corporate-action treatment where relevant
missing-data treatment
```

If the dataset changes:

```text new DatasetVersion.
```

---

# 9. Data Immutability

Once an experiment starts:

```text DatasetVersion
```

is frozen.

Cleaning or preprocessing cannot be changed mid-experiment without creating a new experiment.

---

# 10. Historical Boundary

Every experiment explicitly declares:

```text DevelopmentPeriod
ValidationPeriod
TestPeriod
FinalHoldoutPeriod
```

The chronological ordering must satisfy:

```text Development < Validation < Test < FinalHoldout.
```

No future period may influence an earlier period's configuration.

---

# 11. Final Holdout

The final holdout is protected from research.

It must not be used for:

```text feature selection
parameter tuning
threshold selection
model selection
strategy modification
debugging
```

until the development process is formally complete.

---

# 12. Why the Holdout Matters

Suppose we test:

```text Version A
Version B
Version C
...
Version Z.
```

and choose the version that performs best on the test period.

That test period has now become another training mechanism.

Therefore:

```text repeated test usage
=
hidden training.
```

The final holdout exists specifically to prevent this.

---

# 13. Experiment Families

Experiments are grouped into families.

For example:

```text EXP-FAMILY-PROBABILITY
EXP-FAMILY-EXECUTION
EXP-FAMILY-RISK
EXP-FAMILY-MODE
```

This allows us to measure how much research has been performed in each area.

---

# 14. Multiple Testing Registry

Every tested candidate must be recorded.

Suppose we test:

```text five horizons
ten thresholds
six quantiles.
```

We record all combinations.

We do not record only the winning configuration.

---

# 15. Failed Experiments Matter

A failed experiment remains part of the research history.

For example:

```text Experiment 037
Result: rejected.
```

It is not deleted because:

```text "it didn't work."
```

This prevents repeatedly rediscovering the same noise.

---

# 16. Experiment Lineage

Every experiment records its parent where applicable.

For example:

```text EXP-041
    |
    +-- based on EXP-032
    +-- added feature X
    +-- removed feature Y
```

This creates a research lineage.

---

# 17. No Untracked Experiments

A researcher cannot legitimately say:

```text "I tried another threshold manually."
```

and then include the result in the final strategy without registering that experiment.

Unregistered experiments are treated as exploratory only.

---

# 18. Exploratory Versus Confirmatory Research

We explicitly distinguish:

```text EXPLORATORY
```

from:

```text CONFIRMATORY.
```

Exploratory research is allowed to generate hypotheses.

Confirmatory research tests a previously specified hypothesis.

A result discovered during exploration cannot automatically be presented as confirmatory evidence.

---

# 19. Exploratory Phase

During exploration we may inspect:

```text feature relationships
time-of-day behavior
regime behavior
parameter surfaces
trade distributions
execution behavior.
```

But these observations do not constitute independent validation evidence if they were used to redesign the strategy.

---

# 20. Confirmatory Phase

Once a candidate strategy is defined:

```text specification frozen
dataset boundaries frozen
evaluation protocol frozen
```

the next data is treated as confirmatory evidence.

---

# 21. Walk-Forward Experiment

The standard experiment structure is:

```text TRAIN
   |
   v
CALIBRATE
   |
   v
VALIDATE
   |
   v
FREEZE
   |
   v
FORWARD TEST
   |
   v
ADVANCE
```

The procedure repeats chronologically.

---

# 22. Training

Training can estimate:

```text empirical distributions
probability calibration
learned thresholds
execution-cost distributions
risk parameters
```

only from eligible historical information.

---

# 23. Validation

Validation determines:

```text which candidate should be promoted.
```

It must not be confused with training.

---

# 24. Forward Test

The forward period represents simulated production.

During this period:

```text parameters frozen
model frozen
feature definitions frozen
decision rules frozen
```

unless the predefined architecture explicitly permits scheduled adaptation.

---

# 25. Scheduled Adaptation

If the architecture permits periodic retraining:

```text retraining occurs only at predefined boundaries.
```

It cannot occur simply because:

```text performance looks bad.
```

unless a degradation-trigger mechanism was itself validated beforehand.

---

# 26. Adaptive Trigger Research

If we eventually introduce:

```text "retrain when calibration deteriorates"
```

that trigger becomes a parameterized strategy component.

It must undergo its own walk-forward validation.

It cannot be introduced casually as an operational convenience.

---

# 27. Feature Addition

A new feature requires an experiment.

The experiment must answer:

```text Does the feature provide incremental information
beyond the existing feature set?
```

Not merely:

```text Does adding it increase historical profit?
```

---

# 28. Incremental Information

A feature is valuable if it improves an existing model's ability to distinguish outcomes, calibrate probabilities, or improve economic value after costs.

A feature that merely increases historical P&L through noise is not accepted.

---

# 29. Feature Removal

Feature ablation must also be tested.

For a feature:

```text X
```

compare:

```text FullModel
FullModelWithoutX.
```

The difference estimates the feature's incremental contribution.

---

# 30. Feature Redundancy

Two features may contain almost identical information.

Adding both can increase complexity without increasing predictive information.

Therefore feature correlation and conditional redundancy should be examined.

---

# 31. Feature Leakage Audit

Every feature undergoes:

```text timestamp audit
dependency audit
future-value audit
aggregation audit
label-contamination audit
```

before being admitted to the production feature set.

---

# 32. Label Audit

Every label must specify:

```text LabelStart
LabelEnd
PositiveCondition
NegativeCondition
UnknownCondition
MaturityTime
```

The label must never contain information available only after the prediction timestamp.

---

# 33. Overlapping Label Audit

If labels overlap temporally:

```text overlap structure
```

must be explicitly recorded.

Validation must use appropriate purging/embargo logic where required.

---

# 34. Parameter Search

A parameter search is defined before execution.

For example:

```text Quantile ∈ {q1, q2, q3, q4}
```

The candidate set cannot be expanded after seeing that:

```text q5
```

would have produced a better result, without registering a new experiment.

---

# 35. Grid Search Versus Adaptive Search

Both are permitted in research.

But:

```text more searches
=
more opportunities to find noise.
```

Therefore the total search process must be recorded.

---

# 36. Search Budget

Each experiment family may have a predefined complexity/search budget.

This limits uncontrolled exploration.

The objective is not to search every conceivable combination.

It is to determine whether a simple robust region exists.

---

# 37. Parameter Stability

A selected parameter must be evaluated against nearby values.

For example:

```text θ - δ
θ
θ + δ
```

If performance collapses immediately around `θ`, the parameter is considered fragile.

---

# 38. Parameter Surface

Where feasible, we inspect:

```text parameter value
       vs.
out-of-sample performance
```

We prefer:

```text broad stable region
```

over:

```text isolated optimum.
```

---

# 39. Complexity Penalty

A more complex strategy does not automatically win.

A candidate should be evaluated against:

```text predictive improvement
economic improvement
risk improvement
execution improvement
```

relative to:

```text additional complexity.
```

---

# 40. Baseline Requirement

Every major experiment must have a baseline.

Examples:

```text Simple ORB
Fixed stop
No dynamic mode
No probability calibration
Simple option selection.
```

This answers:

```text Does the new mechanism actually add value?
```

---

# 41. Baseline Preservation

The baseline itself must remain versioned.

If the baseline changes during research, the comparison becomes ambiguous.

---

# 42. Ablation Matrix

The complete system eventually gets tested as:

```text FULL
FULL - MODE
FULL - DYNAMIC RISK
FULL - CONTINUATION
FULL - OPTION FILTER
FULL - EXECUTION FILTER
FULL - PROBABILITY CALIBRATION
```

This tells us which components matter.

---

# 43. Interaction Testing

Some components may only work together.

For example:

```text probability calibration
+
option selection.
```

Therefore the experiment registry must distinguish:

```text individual contribution
```

from:

```text interaction contribution.
```

---

# 44. Null Strategy

We need a meaningful null hypothesis.

A candidate null might preserve:

```text opportunity frequency
time-of-day distribution
position-sizing framework
```

while destroying directional predictive information.

The exact null construction must be carefully designed.

---

# 45. Randomization Tests

Where appropriate, we can test whether observed performance survives randomized alternatives.

For example:

```text shuffle labels
shuffle signals
permute entry assignments
```

But naive shuffling is invalid where temporal dependence matters.

The randomization method must preserve relevant structure.

---

# 46. Temporal Nulls

For financial time series, null construction should respect:

```text temporal dependence
volatility clustering
intraday structure
```

where relevant.

Otherwise the null may be unrealistically easy to reject.

---

# 47. Data-Snooping Detection

We maintain a research ledger containing:

```text number of experiments
number of candidate models
number of parameter configurations
number of feature combinations
number of validation periods examined.
```

This gives us an estimate of how much opportunity existed to discover a spurious winner.

---

# 48. Winner's Curse

If we select:

```text best of many candidates,
```

the observed performance of the winner is expected to be upward-biased.

Therefore:

```text selected historical performance
```

should not be treated as the unbiased expected future performance.

---

# 49. Validation Shrinkage

Where appropriate, the interpretation of a selected candidate should account for selection effects.

We should be conservative when the search space is large relative to the evidence.

---

# 50. Research Stop Rule

Research must eventually stop.

Otherwise:

```text endless experimentation
```

eventually guarantees that some strategy will look extraordinary by chance.

A research program therefore requires a predefined transition from:

```text exploration
```

to:

```text final confirmation.
```

---

# 51. Promotion States

A candidate progresses through:

```text RESEARCH_ONLY
      |
      v
VALIDATED_CANDIDATE
      |
      v
FORWARD_TESTED
      |
      v
FINAL_HOLDOUT
      |
      v
PRODUCTION_CANDIDATE
```

Failure sends it to:

```text REJECTED.
```

---

# 52. Promotion Rule

A candidate may advance only when all mandatory criteria pass.

For example:

```text prediction criterion
+
economic criterion
+
risk criterion
+
execution criterion
+
robustness criterion.
```

One strong metric cannot compensate for failure of a critical invariant.

---

# 53. Rejection Rule

A candidate is rejected if:

```text critical leakage detected
risk invariant violated
execution model invalid
out-of-sample edge absent
drawdown unacceptable
parameter instability extreme
```

The exact numerical thresholds remain to be learned or explicitly specified.

---

# 54. Final Holdout Protocol

When the strategy is declared:

```text DEVELOPMENT COMPLETE
```

the final holdout is executed exactly once under the frozen protocol.

The result is then recorded.

No strategy modification follows from that result while preserving the claim that the holdout was untouched.

---

# 55. Holdout Failure

If the final holdout fails:

```text production candidate = rejected.
```

We do not:

```text modify strategy
rerun holdout
select a new parameter
```

and still call it the same confirmation.

A new research cycle begins with a new candidate.

---

# 56. Paper Trading Boundary

A successful historical candidate does not immediately become live capital.

The progression is:

```text Historical validation
        |
        v
Paper execution
        |
        v
Live shadow monitoring
        |
        v
Limited capital
        |
        v
Production scale.
```

The exact operational thresholds will be specified later.

---

# 57. Paper Trading

Paper trading tests:

```text data arrival
state reconstruction
signal timing
order generation
execution assumptions
latency
operational reliability
```

It cannot prove historical statistical edge by itself.

---

# 58. Shadow Mode

In shadow mode:

```text system generates decisions
```

without sending real orders.

The objective is to compare:

```text predicted execution
vs.
actual market behavior.
```

---

# 59. Live Small-Capital Validation

If historical and paper evidence remain positive, a limited live deployment can test:

```text real execution
real slippage
real latency
real broker behavior
```

with constrained risk.

This is operational validation, not a substitute for historical evidence.

---

# 60. Research Versioning

The complete system receives version identifiers for:

```text DataVersion
FeatureVersion
LabelVersion
ModelVersion
ParameterVersion
ExecutionVersion
StrategyVersion
ExperimentVersion
```

A final result must be reproducible from these versions.

---

# 61. Reproducibility Contract

Given:

```text DatasetVersion
CodeVersion
ModelVersion
ParameterVersion
ExperimentID
RandomSeed where applicable
```

the experiment should reproduce the same result within documented numerical tolerances.

---

# 62. Determinism

The core event-driven state machine should be deterministic.

Given:

```text identical canonical event stream
+
identical initial state
+
identical versions,
```

it must produce:

```text identical state transitions
```

subject only to explicitly nondeterministic external execution components.

---

# 63. Research Audit Log

Every experiment records:

```text ExperimentID
TimestampStarted
TimestampCompleted
Researcher/SystemVersion
Hypothesis
DatasetVersion
FeatureVersion
LabelVersion
ParameterSearchSpace
EvaluationProtocol
Results
Decision
Reason
```

---

# 64. Result Integrity

Raw experiment results must be immutable.

If an analysis changes:

```text AnalysisVersion++
```

The original result remains intact.

This prevents accidental rewriting of evidence.

---

# 65. Research Decision Log

Every important decision receives a rationale:

```text Decision:
Reject Feature X

Reason:
No incremental out-of-sample improvement
and increased execution dependency.
```

This creates an intellectual audit trail.

---

# 66. Negative Knowledge

Rejected hypotheses are valuable.

For example:

```text Dynamic parameter update every minute
→ rejected
```

because:

```text unstable
high turnover
no robust improvement.
```

That knowledge should remain permanently available.

---

# 67. Research Contamination Rule

If a researcher sees a test result and then changes:

```text model
feature
parameter
label
evaluation metric
```

the test is considered contaminated.

It becomes:

```text development evidence,
```

not:

```text untouched test evidence.
```

---

# 68. Multiple Researchers / Agents

If different research processes independently test ideas, all experiments must enter the same registry.

Otherwise the system can unknowingly perform:

```text hidden multiple testing.
```

This is especially important if we later automate experimentation.

---

# 69. Automated Research Constraint

Automation does not remove statistical discipline.

An automated system running:

```text 100,000 parameter combinations
```

is not more scientifically valid than a human running:

```text 100 combinations.
```

In fact, the multiple-testing problem becomes substantially worse.

---

# 70. No Autonomous Strategy Modification

The live strategy cannot automatically modify itself based on arbitrary observed performance.

Any adaptive mechanism must itself be:

```text mathematically specified
+
historically validated
+
walk-forward tested
+
versioned.
```

This preserves the distinction between:

```text adaptive model
```

and:

```text uncontrolled optimization.
```

---

# 71. Research Metrics Hierarchy

The final evaluation hierarchy is:

```text LEVEL 1
Data validity

LEVEL 2
Causal correctness

LEVEL 3
Prediction quality

LEVEL 4
Economic value

LEVEL 5
Execution robustness

LEVEL 6
Risk robustness

LEVEL 7
Out-of-sample performance

LEVEL 8
Adversarial robustness

LEVEL 9
Operational reproducibility
```

A failure at a lower level cannot be hidden by success at a higher level.

---

# 72. Example of Correct Research

Suppose we hypothesize:

```text "Opening-range expansion predicts stronger continuation." id="9q6qyp"
```

We define:

```text feature
label
horizon
training window
validation window
primary metric
candidate threshold set
```

before running the experiment.

Then:

```text train
→ validate
→ freeze
→ forward test.
```

Only after the forward result is recorded do we interpret it.

---

# 73. Example of Incorrect Research

This is prohibited:

```text Try threshold 0.5
Bad.

Try 0.6
Better.

Try 0.7
Excellent.

Try 0.75
Excellent.

Try different stop
Even better.

Try another horizon
Great.

Declare strategy validated.
```

This is textbook researcher degrees-of-freedom inflation.

The final "excellent" result is not independent evidence.

---

# 74. Research Budget

The strategy should maintain an explicit count of:

```text features tested
labels tested
horizons tested
parameter combinations
model variants
execution assumptions
```

This becomes part of the final evidence report.

---

# 75. Evidence Grading

The final strategy report should distinguish:

```text OBSERVED FACT
DERIVED RESULT
VALIDATED EMPIRICAL RESULT
MODEL ASSUMPTION
RESEARCH HYPOTHESIS
UNRESOLVED QUESTION
```

This prevents assumptions from being mistaken for facts.

---

# 76. Final Research Report

At the end of the research program, the report should contain:

```text Strategy definition
Data provenance
Experiment history
Feature registry
Label registry
Parameter registry
Walk-forward methodology
Final candidate
Rejected alternatives
Out-of-sample results
Final holdout result
Risk analysis
Execution analysis
Stress analysis
Adversarial analysis
Known limitations
```

---

# 77. No "Best Strategy" Claim Without Context

We should never say:

```text "This is the best strategy."
```

based solely on historical performance.

The strongest legitimate statement would be something like:

```text "Under the specified historical data,
execution assumptions,
walk-forward methodology,
and validation protocol,
this candidate demonstrated statistically and economically
credible out-of-sample performance."
```

Even that statement requires the evidence.

---

# 78. Canonical Research Invariants

```text RES-001
Every experiment has an immutable identity.

RES-002
Every experiment has a predefined hypothesis.

RES-003
Primary metrics are defined before results are observed.

RES-004
Dataset versions are immutable during an experiment.

RES-005
Final holdout data cannot influence development.

RES-006
All tested candidates are recorded.

RES-007
Failed experiments are retained.

RES-008
Exploratory and confirmatory evidence are separated.

RES-009
Parameter search spaces are recorded.

RES-010
Multiple testing is explicitly tracked.

RES-011
Counterfactuals cannot replace historical outcomes.

RES-012
Adaptive mechanisms require independent validation.

RES-013
A test contaminated by post-result modification is no longer a clean test.

RES-014
A profitable result does not automatically constitute an edge.

RES-015
The final candidate must survive out-of-sample and adversarial evaluation.
```

---

# 79. Architecture Status

The system now has two distinct feedback loops.

The first is the **market-learning loop**:

```text MARKET
   ↓
OBSERVATION
   ↓
STATE
   ↓
PREDICTION
   ↓
TRADE
   ↓
OUTCOME
   ↓
MATURED LABEL
   ↓
LEARNING
```

The second is the **research-validation loop**:

```text HYPOTHESIS
   ↓
EXPERIMENT
   ↓
WALK-FORWARD TEST
   ↓
RESULT
   ↓
VALIDATION
   ↓
PROMOTION / REJECTION
```

These must never be confused.

The first is part of the strategy.

The second governs how we are allowed to modify the strategy.

---

# 80. What We Have Now

The architecture is now substantially complete at the conceptual level:

```text DATA CONTRACT
STATE MODEL
VARIABLE REGISTRY
DEPENDENCY GRAPH
STATE TRANSITIONS
LABEL SPECIFICATION
PARAMETER LEARNING
TRADE LIFECYCLE
EXECUTION MODEL
PERFORMANCE MODEL
RESEARCH VALIDATION
```

The remaining work is increasingly about **formal integration and verification**, not inventing more trading logic.

---

# 81. Next Artifact

The next artifact should therefore be the:

# CANONICAL SYSTEM INVARIANT AND FORMAL VERIFICATION SPECIFICATION

This will consolidate every invariant we have discovered into one machine-checkable-style contract.

We will attack questions such as:

```text Can the state machine enter an impossible state?

Can position quantity become negative?

Can protection decrease?

Can a future event influence a historical decision?

Can a label become eligible too early?

Can a parameter update during a frozen period?

Can an order create exposure without a fill?

Can an exit occur without an exit obligation?

Can a model promotion rewrite an active trade?

Can duplicated events change P&L twice?

Can a missing field silently become zero?

Can the learner accidentally train on test information?

Can risk increase merely because the mode changes?
```

That will be our **formal safety layer** before implementation.

After that, we can move toward the final integrated specification and eventually the implementation boundary, where the TrueData documentation becomes the remaining external dependency.