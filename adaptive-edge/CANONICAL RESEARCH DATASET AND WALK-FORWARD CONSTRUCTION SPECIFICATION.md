# CANONICAL RESEARCH DATASET AND WALK-FORWARD CONSTRUCTION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how historical market data becomes research data without introducing temporal leakage.

The pipeline is:

```text
Raw Historical Data
        ↓
Canonical Events
        ↓
Causal State Reconstruction
        ↓
Opportunity Observations
        ↓
Future Outcome Observation
        ↓
Matured Labels
        ↓
Eligible Research Dataset
        ↓
Walk-Forward Training
        ↓
Validation
        ↓
Forward Evaluation
```

The fundamental rule is:

```text
A historical decision may use only information that was causally available
at the timestamp of that decision.
```

---

# 2. Research Dataset Is Not the Raw Dataset

The raw dataset contains observations.

The research dataset contains:

```text
what was known
when it was known
what decision could have been made
what subsequently happened
```

These are fundamentally different objects.

---

# 3. Immutable Raw Data

Raw provider data is treated as immutable.

Conceptually:

```text
RawDatasetVersion
```

contains:

```text source
provider
download/extraction timestamp
source version
instrument universe
date range
raw records
```

Raw data must never be silently modified after ingestion.

Corrections create a new dataset version.

---

# 4. Canonical Dataset

The raw dataset is transformed into:

```text CanonicalEventDataset
```

with:

```text canonical event schema
canonical timestamps
canonical instrument identifiers
provider provenance
data-quality status.
```

This is the dataset consumed by the strategy engine.

---

# 5. Dataset Versioning

Every research dataset receives:

```text DatasetVersion
```

A dataset version is immutable.

If:

```text source data changes
mapping changes
cleaning logic changes
instrument universe changes
```

then a new dataset version is created.

Historical experiment results continue referencing the old version.

---

# 6. Data Cleaning Principle

Cleaning is allowed only when it preserves known historical semantics.

Examples of potentially valid operations:

```text type normalization
unit normalization
symbol mapping
duplicate removal when duplication is demonstrably identifiable
documented corporate/instrument corrections
```

The system must not perform:

```text hindsight-based price correction
future-aware filtering
performance-driven data cleaning.
```

---

# 7. Missing Data

Missing data remains missing.

The system must not fill missing observations using information that would not have been available at the time.

For example:

```text future price
    ↓
backfilled missing historical price
```

is prohibited.

---

# 8. Causal Replay

The canonical historical dataset is replayed chronologically:

```text E1
E2
E3
...
En
```

The same state-transition engine used by the eventual runtime reconstructs historical state.

This is important.

We do not create a separate "backtest interpretation" of the strategy.

---

# 9. Research/Runtime Equivalence

The preferred architecture is:

```text Historical Events
        ↓
Same State Engine
        ↓
Same Feature Engine
        ↓
Same Decision Engine
```

with only:

```text historical execution adapter
```

replacing live execution.

This minimizes research/live divergence.

---

# 10. Decision Observation

At each eligible decision timestamp `t`, create an:

```text OpportunityObservation_t
```

containing only information available at `t`.

Conceptually:

```text OpportunityObservation {
    OpportunityID
    Timestamp
    StateSnapshot
    FeatureSnapshot
    ProbabilityInputs
    CandidateOptions
    DataQuality
    RuntimeVersion
}
```

---

# 11. Information Set

Define:

```text F_t
```

as the complete information set available at decision time `t`.

Then:

```text Decision_t = f(F_t)
```

No variable outside:

```text F_t
```

may influence the decision.

---

# 12. Future Information

Define:

```text Future_t
```

as information whose causal availability occurs after `t`.

Then:

```text Future_t ∩ F_t = ∅
```

for the purposes of decision generation.

Future information may later be used for:

```text outcome measurement
label construction
```

but never for reconstructing:

```text Decision_t.
```

---

# 13. Opportunity Population

Not every market event becomes an opportunity.

The opportunity population is defined by the strategy's structural eligibility conditions.

Conceptually:

```text OpportunityEligible_t
=
g(F_t)
```

The function must be fully causal.

---

# 14. Opportunity Timestamp

The opportunity timestamp is the earliest timestamp at which all required entry information exists.

This prevents a subtle form of look-ahead:

```text identifying an opportunity using a condition that was only known
after the supposed entry timestamp.
```

---

# 15. Entry Observation

For every eligible opportunity, store:

```text EntryInformationSnapshot
```

including:

```text market state
feature state
probability state
candidate option state
economic state
risk state
runtime version.
```

This snapshot is immutable.

---

# 16. Trade Versus Opportunity Dataset

The research dataset must contain both:

```text traded opportunities
```

and:

```text NO_TRADE opportunities.
```

Otherwise the model learns only from selected trades.

That creates selection bias.

---

# 17. No-Trade Observations

A no-trade observation records:

```text OpportunityID
timestamp
available evidence
probability
economic state
candidate option state
NoTradeReason.
```

No position is created.

---

# 18. Why No-Trade Records Matter

The system must learn the distinction between:

```text favorable opportunity
```

and:

```text apparently favorable but economically invalid opportunity.
```

Examples:

```text high directional probability
but excessive option spread

good direction
but insufficient expected value

valid setup
but unavailable risk budget.
```

---

# 19. Future Observation Window

Every label defines a future observation window:

```text [T_start, T_end]
```

where:

```text T_start >= OpportunityTimestamp.
```

The exact horizon is a parameter of the label definition, not an arbitrary implementation constant.

---

# 20. Label Maturity

A label is unavailable until:

```text current historical replay time >= T_end
```

or until every other required future observation has become available.

Before that:

```text LabelStatus = IMMATURE.
```

---

# 21. Label Construction

Conceptually:

```text Label_t
=
L(
Opportunity_t,
FutureEvents_(t,T_end)
)
```

The label may use future data because the label describes the outcome.

But the future data is causally separated from the original opportunity.

---

# 22. Label/Feature Separation

The training observation therefore has two temporal regions:

```text PAST / PRESENT
        |
        +--> Features
        +--> Decision inputs
        |
        boundary T
        |
        +--> FUTURE
             |
             +--> Outcome
             +--> Label
```

The boundary is absolute.

---

# 23. Example

Suppose:

```text Opportunity = 10:00
Observation horizon = 30 minutes
```

Then:

```text Features:
information available <= 10:00

Label:
information observed through 10:30.
```

The label is not eligible for training until the relevant future information has matured.

---

# 24. Multiple Horizons

The architecture may support multiple future horizons:

```text H1
H2
H3
...
```

For example, conceptually:

```text short continuation
medium continuation
extended continuation.
```

But each horizon receives a separate label definition.

They must not be conflated.

---

# 25. Expected Horizon Versus Label Horizon

These remain distinct.

```text Label Horizon
=
future observation interval used to determine an outcome.

Expected Horizon
=
model prediction about how long the current opportunity may remain economically favorable.
```

The first is an observation design parameter.

The second is a model output.

---

# 26. Positive and Negative Labels

Every learned quantity must explicitly define:

```text positive outcome
negative outcome
neutral/invalid outcome
```

before estimation begins.

The system must not choose the label definition after seeing which formulation produces the best backtest.

---

# 27. Outcome Definition

An outcome may depend on:

```text price path
maximum favorable excursion
maximum adverse excursion
terminal P&L
time to threshold
protection event
continuation state
```

But each must be specified mathematically before the corresponding research experiment.

---

# 28. Path-Dependent Labels

For path-dependent outcomes, the complete future event sequence within the defined horizon is used.

For example:

```text MaximumFavorableExcursion_t
=
max future favorable movement
```

subject to the exact reference price definition.

---

# 29. Maximum Adverse Excursion

Similarly:

```text MaximumAdverseExcursion_t
=
max adverse movement
```

within the defined observation window.

These quantities describe the future outcome.

They cannot be fed into the original decision.

---

# 30. Profit-Floor Label

The profit-floor distribution is constructed from eligible historical outcomes.

Conceptually:

```text X_t = defined future economic outcome
```

Then:

```text ProfitFloor = Quantile_q(X)
```

where:

```text q
```

is not yet numerically fixed.

---

# 31. Quantile Selection

The quantile must be selected through:

```text training-only evidence
+
walk-forward validation
```

and must not be selected by inspecting the final holdout.

---

# 32. Continuation Label

Continuation labels determine whether an opportunity remains favorable over a future interval.

Conceptually:

```text ContinuationLabel_t
=
1
if predefined continuation condition occurs
0
otherwise.
```

The exact condition is part of the label-definition version.

---

# 33. Reversal Label

The reversal label identifies whether the original directional thesis becomes invalid or reverses during the future observation window.

It must be defined independently from:

```text current model probability.
```

Otherwise the model could end up labeling itself.

---

# 34. Emergency-Reversal Training Population

The emergency-reversal model must be trained from historical situations where:

```text original directional state was valid
+
subsequent adverse reversal occurred.
```

The event definition must be fixed before model estimation.

---

# 35. Selection of Training Population

Training observations are selected according to:

```text EligibilityRule
```

defined before model fitting.

We cannot say:

```text choose only historically successful setups.
```

That would introduce selection bias.

---

# 36. Training Dataset

At training cutoff `C`:

```text TrainingSet_C
```

contains only observations satisfying:

```text OpportunityTimestamp < C
LabelMaturityTime <= C
```

and all other eligibility rules.

---

# 37. Critical Training Rule

The following must hold:

```text LabelMaturityTime <= TrainingCutoff.
```

An observation whose label is not mature by the training cutoff cannot enter training.

---

# 38. Validation Dataset

Validation data is chronologically later than training.

Conceptually:

```text Training
    <
Validation
```

The validation set must not influence parameter fitting before evaluation.

---

# 39. Forward Evaluation

After model/parameter selection:

```text ForwardWindow
```

is evaluated without using its outcomes to modify the model being tested.

This is the first meaningful out-of-sample measurement.

---

# 40. Walk-Forward Structure

The research process becomes:

```text Fold 1:

TRAIN | VALIDATE | FORWARD
-------|----------|--------

Fold 2:

TRAIN --------| VALIDATE | FORWARD
--------------|----------|--------

Fold 3:

TRAIN ----------------| VALIDATE | FORWARD
----------------------|----------|--------
```

The actual window lengths remain unfrozen.

---

# 41. Parameter Fitting

For each walk-forward fold:

```text Fit parameters
```

using only the training population.

Parameters may include:

```text probability calibration
distribution parameters
profit-floor quantile
continuation threshold
reversal threshold
state sensitivity
risk coefficients
execution-cost estimates
```

only where the research specification permits them to be learned.

---

# 42. Validation Selection

Validation may be used to select among:

```text candidate parameter configurations
candidate model variants
candidate structural alternatives
```

subject to the predefined research protocol.

---

# 43. Forward Window Lock

Once the forward window begins:

```text model parameters are frozen.
```

No tuning based on forward outcomes is allowed.

---

# 44. Forward Results

The forward period produces:

```text ForwardPredictions
ForwardDecisions
ForwardExecution
ForwardOutcomes
ForwardMetrics.
```

These are stored immutably.

---

# 45. Fold Advancement

After a forward period completes:

```text future data becomes historical.
```

It may become eligible for subsequent training according to the walk-forward procedure.

This is the correct temporal evolution.

---

# 46. No Retroactive Training

A model used in Fold `k` cannot be retroactively retrained using Fold `k`'s forward outcomes and still be described as the same model.

That would contaminate the evaluation.

---

# 47. Expanding Versus Rolling Training

Two legitimate architectures exist:

```text EXPANDING
all eligible history up to cutoff

ROLLING
only a bounded recent historical window.
```

The architecture supports both.

The choice must be determined empirically and specified before final evaluation.

---

# 48. Training Window Length

The training window length is therefore:

```text UNFROZEN.
```

It must not be selected because one particular length happens to maximize historical P&L.

Its selection requires a predefined model-selection protocol.

---

# 49. Validation Window Length

Likewise:

```text UNFROZEN.
```

The validation horizon must be sufficient to distinguish parameter stability from random noise.

The final numerical value belongs to the research protocol.

---

# 50. Forward Window Length

The forward evaluation horizon is also:

```text UNFROZEN.
```

It must represent a genuinely unseen period rather than merely another tuning segment.

---

# 51. Gap / Embargo

Where labels overlap across observations, an embargo or purging rule may be required.

For example:

```text Observation A:
future label window overlaps
Observation B's training boundary.
```

Those observations cannot always be treated as independent.

---

# 52. Purging Rule

If an observation's future label window crosses a dataset boundary:

```text it is excluded from the affected training/validation population
```

unless the research design explicitly permits it.

This prevents temporal contamination.

---

# 53. Label Overlap

Suppose:

```text Opportunity A = 10:00
Label end = 11:00

Opportunity B = 10:30
Label end = 11:30
```

These observations share future information.

The research framework must explicitly account for this dependence.

It cannot blindly treat them as independent samples.

---

# 54. Sample Independence

The statistical methodology must therefore distinguish:

```text number of observations
```

from:

```text effective independent information.
```

Tick-level data can create enormous observation counts without providing equivalent independent samples.

---

# 55. Tick Explosion Problem

One market move can generate:

```text thousands of ticks.
```

Those ticks are not thousands of independent opportunities.

Therefore the research framework must avoid interpreting raw tick count as statistical sample size.

---

# 56. Opportunity Sampling

The model's effective observation unit should be the canonical:

```text OpportunityObservation
```

rather than every incoming tick.

Ticks may update state.

They do not automatically create independent labels.

---

# 57. TBT Versus Minute Dataset

The research system should support two information regimes:

```text Dataset A:
minute-derived information

Dataset B:
minute + TBT-derived information.
```

Both must use the same:

```text opportunity definitions
labels
walk-forward boundaries
cost assumptions
evaluation metrics.
```

---

# 58. Incremental Value Test

The question is:

```text Does TBT add statistically robust out-of-sample information?
```

not:

```text Does TBT produce a higher backtest number?
```

The comparison must include:

```text net performance
calibration
drawdown
execution sensitivity
stability
complexity cost.
```

---

# 59. Execution Data Separation

Historical market observations and modeled execution are separate datasets:

```text MarketDataset
ExecutionModel.
```

The execution model must not be calibrated using the same forward outcomes it is later used to evaluate.

---

# 60. Cost Model Training

If execution costs are learned historically, the cost model itself must follow the same temporal protocol:

```text training data
→ validation
→ forward evaluation.
```

It cannot use future execution behavior to improve historical simulated fills.

---

# 61. No Performance-Based Cleaning

Suppose a historical period produces poor results.

The research system cannot remove it because:

```text data looked unusual
```

unless a pre-existing data-quality rule objectively identifies the data as invalid.

---

# 62. Regime Labels

Market regimes may be constructed for analysis.

However:

```text regime definition
```

must be determined independently of future strategy performance.

Otherwise regime analysis becomes another form of hindsight optimization.

---

# 63. Feature Availability

Every feature must have:

```text FeatureTimestamp
```

and:

```text SourceInformationSet.
```

A feature is eligible for decision `t` only if:

```text FeatureTimestamp <= t.
```

---

# 64. Historical Distribution Availability

An empirical distribution used at time `t` must be constructed from observations satisfying:

```text ObservationTimestamp < t
```

and:

```text LabelMaturityTime <= t.
```

This is the formal anti-lookahead rule for learned historical distributions.

---

# 65. Bayesian Updating

If Bayesian updating is used:

```text Prior_t
```

must be derived only from information eligible at `t`.

Posterior updating can consume:

```text current evidence
```

but not:

```text future outcomes.
```

---

# 66. Statistical Model Version

Every model fit receives:

```text ModelVersion
```

with:

```text training dataset version
training cutoff
feature version
label version
parameter version
algorithm version.
```

---

# 67. Parameter Version

Every parameter set receives:

```text ParameterVersion
```

and:

```text TrainingFoldID.
```

The parameter set is immutable.

---

# 68. Experiment Version

Every research experiment records:

```text ExperimentID
DatasetVersion
FeatureVersion
LabelVersion
ModelVersion
ParameterSearchSpace
TrainingProtocol
ValidationProtocol
ForwardProtocol
ExecutionPolicyVersion
RandomSeed, if applicable.
```

---

# 69. Multiple Testing

If the research process evaluates:

```text 100 candidate parameter sets
```

the experiment records all 100.

It cannot report:

```text best parameter set
```

without preserving the selection process.

---

# 70. Search-Space Discipline

The allowed parameter search space must be declared before final forward evaluation.

For example:

```text permitted quantile range
permitted lookback range
permitted threshold range
```

must be specified independently of forward performance.

The exact ranges remain:

```text UNFROZEN.
```

---

# 71. Model Complexity Control

The baseline model remains statistically simple.

Candidate complexity must be justified by:

```text incremental out-of-sample evidence
```

rather than in-sample improvement.

No neural network, reinforcement learning system, or LLM is introduced into the baseline research pipeline.

---

# 72. Baseline Model

The first benchmark must be:

```text simple empirical/statistical model.
```

This provides the reference against which future complexity can be evaluated.

A complex model that cannot materially outperform the baseline after costs has no justification.

---

# 73. Performance Evaluation

The forward evaluation must include more than P&L.

At minimum, research should record:

```text net P&L
drawdown
trade count
win/loss distribution
expectancy
profit factor
cost contribution
slippage sensitivity
parameter stability
probability calibration
```

Exact reporting thresholds are not yet frozen.

---

# 74. Statistical Uncertainty

Every major performance estimate should have uncertainty information where statistically appropriate.

A result such as:

```text +₹X
```

without uncertainty is insufficient evidence of an edge.

---

# 75. Dependency-Aware Evaluation

Because observations may be temporally dependent, confidence estimates must account for:

```text overlapping labels
serial correlation
clustered opportunities
market regimes.
```

Simple IID assumptions must not be applied blindly.

---

# 76. Forward Result Immutability

Once a forward fold is evaluated:

```text ForwardResultVersion
```

is immutable.

Later model development cannot rewrite the result.

---

# 77. Final Holdout

A final untouched period may be retained after development.

Its purpose is:

```text confirmation of the complete research process.
```

Once inspected, it is no longer a clean holdout.

---

# 78. Holdout Contamination

The following contaminate the holdout:

```text tuning parameters using holdout
changing labels after seeing holdout
changing features after seeing holdout
choosing model architecture after seeing holdout
re-running repeatedly until a favorable result appears.
```

---

# 79. Research Stopping Rule

The research process must eventually define when experimentation stops.

Otherwise:

```text repeated searching
```

can eventually discover apparent edges by chance.

A stopping protocol is therefore part of the statistical design.

---

# 80. Research Ledger

Every experiment is recorded in:

```text ExperimentLedger
```

including:

```text experiment ID
hypothesis
dataset
parameter space
result
decision
reason for continuation/rejection.
```

This prevents selective memory of successful experiments.

---

# 81. Canonical Temporal Rule

The entire research system obeys:

```text At decision time t:

Allowed:
Information with causal availability <= t

Forbidden:
Information with causal availability > t

Allowed later:
Future information for outcome labeling

Forbidden permanently:
Future information entering the original decision.
```

---

# 82. Research Dataset Invariants

```text RDS-001
Raw datasets are immutable.

RDS-002
Canonical datasets are versioned.

RDS-003
Every opportunity has a causal timestamp.

RDS-004
Features use only information available at the opportunity timestamp.

RDS-005
Labels may use future information only after the opportunity has been fixed.

RDS-006
Labels must mature before entering training.

RDS-007
Training data ends chronologically before validation/forward data.

RDS-008
Forward parameters are frozen before forward evaluation.

RDS-009
No-trade observations are retained.

RDS-010
Overlapping future labels are explicitly handled.

RDS-011
Tick count is not treated as independent sample count.

RDS-012
Model versions are immutable.

RDS-013
Parameter versions are immutable.

RDS-014
Forward results are immutable.

RDS-015
Holdout data cannot influence development.

RDS-016
Performance-based data cleaning is prohibited.

RDS-017
Execution models are temporally validated independently.

RDS-018
Every research result is reproducible from versioned inputs.
```

---

# 83. Current Architecture Status

The following is now structurally complete:

```text Mathematical Specification          COMPLETE
Variable Registry                      COMPLETE
Event Schema                           COMPLETE
State Schema                           COMPLETE
State Transition Specification         COMPLETE
Verification Plan                      COMPLETE
Data-to-Event Contract                 COMPLETE
Research Dataset Contract              COMPLETE
Temporal Walk-Forward Logic             COMPLETE
```

Still intentionally unresolved:

```text exact training-window length
exact validation-window length
exact forward-window length
exact embargo length
exact label horizons
exact quantiles
exact thresholds
exact feature lookbacks
exact statistical estimators
```

These are research quantities.

They must be determined empirically under the protocol rather than invented now.

---

# 84. Next Artifact

The next logical artifact is the:

# CANONICAL STATISTICAL ESTIMATION AND CALIBRATION SPECIFICATION

This is where we finally formalize exactly how the historical data becomes the probability and outcome distributions.

We will specify, without yet selecting arbitrary numerical values:

```text empirical probability estimation
conditional distributions
Bayesian updating where justified
probability calibration
sample weighting
smoothing
minimum sample requirements
confidence/uncertainty estimates
distribution stability tests
parameter estimation
quantile estimation
model selection
calibration validation.
```

This is the next place where the "statistically boring and extremely auditable" principle becomes mathematically concrete.