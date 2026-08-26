# HISTORICAL EXPERIMENT MATRIX
## Canonical Research Specification — Version 1.0

## 1. Purpose

The purpose of this artifact is to define exactly:

`WHAT`

must be learned,

`FROM WHICH DATA`

`USING WHICH LABEL`

`OVER WHICH HORIZON`

`WITH WHICH ESTIMATOR`

`UNDER WHICH VALIDATION RULE`

and:

`UNDER WHAT CONDITIONS`

the learned quantity is permitted to enter the production model.

No production parameter is permitted to exist without an experiment definition.

---

# 2. Fundamental Research Unit

The basic research unit is not:

`one tick`.

It is:

`one decision opportunity`.

Define:

`D_t = canonical state at decision timestamp t`.

Each decision opportunity contains:

`State_t`

`AvailableInformation_t`

`CandidateAction_t`

and, after the future becomes observable:

`Outcome_t`.

Therefore:

```text
D_t
 |
 +--> information available at t
 |
 +--> candidate action
 |
 +--> future realized path
 |
 +--> matured labels
```

---

# 3. Decision Opportunity Must Be Causal

At timestamp `t`:

```text
Allowed:
I_<=t

Forbidden:
I_>t
```

This remains true even inside historical research.

---

# 4. Sampling Unit

We will not necessarily create a training observation for every tick.

That would create enormous temporal dependence.

Instead we define:

`DecisionCandidate_t`.

A candidate is generated when the canonical state satisfies the minimum observation requirements for evaluating the strategy.

---

# 5. Candidate Generation

Candidate generation must itself be deterministic.

For example:

```text
MarketState valid
AND
OptionUniverse valid
AND
ExecutionState valid
AND
No existing conflicting position
```

then:

`DecisionCandidate = TRUE`.

The exact entry candidate conditions are inherited from the frozen strategy architecture.

---

# 6. Why Candidate Sampling Matters

Suppose there are:

`10,000,000 ticks`.

If every tick becomes an independent observation, the statistical system may falsely believe it has:

`10,000,000 samples`.

But many consecutive ticks represent essentially the same market episode.

Therefore we distinguish:

`N_events`

from:

`N_decision_opportunities`

from:

`N_effective_samples`.

---

# 7. Event-Level Data

Tick data is primarily required for:

`state reconstruction`

`event ordering`

`microstructure`

`execution`

`MFE`

`MAE`

and:

`short-horizon outcome measurement`.

It is not automatically required for every statistical parameter.

---

# 8. Minute-Level Data

Minute data may be sufficient for some:

`medium-horizon`

`volatility`

`session`

`range`

and:

`historical regime`

experiments.

We should use the lowest temporal resolution that preserves the information required by the experiment.

This reduces unnecessary complexity.

---

# 9. Experiment Classes

The research matrix is divided into:

`E1 — Data Integrity`

`E2 — Feature Validation`

`E3 — Probability`

`E4 — Horizon`

`E5 — Economic Value`

`E6 — Option Selection`

`E7 — Protection`

`E8 — Execution`

`E9 — Capability Degradation`

`E10 — Regime Stability`

`E11 — Model Combination`

`E12 — Final Walk-Forward`.

---

# 10. E1 — Data Integrity Experiments

Before learning anything:

we verify that the source data can reconstruct the required state.

Tests include:

`timestamp continuity`

`duplicate detection`

`out-of-order events`

`invalid quotes`

`missing events`

`instrument identity`

`session boundaries`

`option contract lifecycle`.

No predictive experiment starts until this layer passes.

---

# 11. E1.1 — Timestamp Integrity

Measure:

`timestamp resolution`

`duplicate timestamps`

`event ordering`

`clock discontinuities`.

Output:

`TimestampQualityDistribution`.

---

# 12. E1.2 — Feed Gap Distribution

Measure:

`gap duration`

`gap frequency`

`gap by session phase`

`gap by instrument`.

Output:

`DataAvailabilityDistribution`.

This becomes an input to capability modeling.

---

# 13. E1.3 — Quote Integrity

Measure:

`negative spread`

`crossed market`

`zero/invalid values`

`bid > ask`

`LTP outside plausible quote state`.

Output:

`QuoteValidityRate`.

---

# 14. E1.4 — Duplicate Events

Measure:

`duplicate event frequency`.

If duplicates exist:

determine whether they are:

`exact duplicates`

or:

`retransmissions with changed metadata`.

The canonical event identity must be established before feature calculation.

---

# 15. E1.5 — Option Contract Integrity

For every candidate option:

verify:

`symbol`

`expiry`

`strike`

`instrument type`

`tradability interval`.

This prevents historical contract contamination.

---

# 16. E2 — Feature Validation

Before asking whether a feature predicts anything:

we determine whether it is:

`stable`

`available`

`causal`

and:

`reconstructable`.

---

# 17. E2.1 — Price Features

Candidate quantities:

`return`

`velocity`

`acceleration`

`range`

`rolling range`

`realized volatility`

`distance from session reference`

`distance from rolling reference`.

Each feature receives:

`availability`

`stability`

`distribution`

`missingness`.

---

# 18. E2.2 — Flow Features

Potential quantities:

`trade imbalance`

`signed volume`

`volume acceleration`

`buy/sell pressure`

`flow persistence`.

But a flow feature is admitted only if the underlying trade classification is semantically valid.

---

# 19. E2.3 — Order-Book Features

Potential quantities:

`bid/ask imbalance`

`depth concentration`

`depth change`

`queue pressure`

`spread`

`spread acceleration`.

Again:

`missing != zero`.

---

# 20. E2.4 — Volatility Features

Potential quantities:

`realized volatility`

`range volatility`

`ATR-like scale`

`short-term variance`

`volatility acceleration`.

The research question is not:

"Which volatility indicator is best?"

It is:

"Which representation contains incremental conditional information?"

---

# 21. E2.5 — Time Features

Potential variables:

`time since open`

`time to close`

`session phase`

`opening-range status`.

These are deterministic causal features.

---

# 22. E2.6 — Liquidity Features

Potential variables:

`spread`

`depth`

`trade frequency`

`quote frequency`

`volume`

`estimated execution cost`.

These become important later for determining whether an apparent signal is economically tradable.

---

# 23. E3 — Probability Experiments

The objective is to estimate:

`P(UP | State_t)`

`P(DOWN | State_t)`

and:

`P(NEUTRAL | State_t)`.

But the output must be calibrated.

---

# 24. E3.1 — Baseline Direction Model

First construct an intentionally simple empirical model.

Example:

```text
Condition:
State belongs to historical neighborhood S

Estimate:
P(UP | S)
P(DOWN | S)
P(NEUTRAL | S)
```

No sophisticated AI.

This establishes the baseline.

---

# 25. E3.2 — Incremental Feature Test

Add one feature domain at a time.

For example:

```text
BASE
BASE + VOLATILITY
BASE + FLOW
BASE + LIQUIDITY
BASE + OPTION
BASE + TIME
```

Measure incremental information.

---

# 26. Feature Admission Rule

A feature is not admitted because:

`correlation > 0`.

It must demonstrate:

`incremental out-of-sample value`.

If removing the feature does not materially degrade the validated model:

the feature is unnecessary.

---

# 27. E3.3 — Calibration Experiment

For each probability bucket:

`0.50–0.55`

`0.55–0.60`

...

measure:

`predicted probability`

versus:

`empirical outcome frequency`.

Output:

`CalibrationCurve`.

---

# 28. E3.4 — Probability Reliability

For each probability estimate:

record:

`P_hat`

`sample support`

`effective sample size`

`confidence/uncertainty`.

A probability without evidence strength is incomplete.

---

# 29. E3.5 — Regime-Conditional Probability

Estimate:

`P(UP | State, VolatilityRegime)`

and:

`P(UP | State, SessionPhase)`.

Compare against:

`P(UP | State)`.

If conditioning provides genuine out-of-sample improvement:

retain it.

Otherwise:

remove it.

---

# 30. E4 — Horizon Experiments

The system must learn:

`P(H | State_t)`.

We are not hardcoding:

`< 45 minutes = scalp`.

---

# 31. Horizon Representation

Possible horizons:

`1 minute`

`2`

`3`

...

up to the operational maximum.

But we do not necessarily need a separate model for every minute.

The distribution can be represented continuously or through validated bins.

---

# 32. Horizon Label

For every historical decision:

measure how long the predicted opportunity remains economically meaningful.

Not simply:

"how long until price changes."

The horizon should be tied to:

`continuation value`.

---

# 33. Horizon Outcome

Define:

`OpportunityPersistence`.

The label answers:

"How long after entry does the expected net opportunity remain positive?"

This is much more useful than raw trade duration.

---

# 34. Horizon Distribution

Estimate:

`P(H <= h | State_t)`.

From this we can derive:

`median horizon`

`upper quantiles`

`probability of short persistence`

`probability of extended persistence`.

---

# 35. Mode Classification

The mode becomes a function of the distribution:

```text
P(H | State)
```

rather than a fixed duration threshold.

Therefore:

`MICRO`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`

are labels over the predicted horizon distribution.

---

# 36. Important Consequence

A trade can have:

`P(H < 5 min) = 0.40`

and:

`P(H < 30 min) = 0.85`.

The system does not need to pretend:

"this trade is exactly a five-minute trade."

It knows the uncertainty.

---

# 37. E5 — Economic Value Experiments

This is where prediction becomes trading.

For each candidate option:

estimate:

`ExpectedGrossReturn`.

Then:

`ExpectedExecutionCost`.

Then:

`ExpectedNetReturn`.

---

# 38. Net Economic Value

Conceptually:

```text
EV_net
=
E[GrossReturn]
-
E[EntryCost]
-
E[ExitCost]
-
E[Slippage]
-
E[Fees]
-
E[OtherKnownCosts]
```

The distributions, rather than only point estimates, matter.

---

# 39. Distributional EV

We therefore estimate:

`P(NetReturn | State, Option)`.

From that distribution:

derive:

`ExpectedNetReturn`

`median`

`lower quantiles`

`upper quantiles`

`probability of loss`.

---

# 40. Conservative EV

A trade should not be accepted merely because:

`E[NetReturn] > 0`.

We also examine downside uncertainty.

A candidate may require:

`E[NetReturn]`

to exceed an uncertainty-adjusted opportunity cost.

The exact criterion is learned.

---

# 41. E6 — Option Selection

The system should compare available CE candidates and PE candidates.

For each candidate:

```text
Option_j
 |
 +--> Directional response
 +--> Premium
 +--> Spread
 +--> Liquidity
 +--> Volatility exposure
 +--> Time decay
 +--> Execution
 +--> Expected net distribution
```

---

# 42. Candidate Universe

The option universe must be reconstructed as it existed at timestamp `t`.

We cannot use:

`today's option chain`

to simulate historical decisions.

---

# 43. Option Ranking

Each candidate receives:

`EconomicScore_j`.

But ranking alone is insufficient.

The selected option must also satisfy:

`Risk`

`Execution`

`Liquidity`

`Data capability`.

---

# 44. CE Versus PE

The final directional choice becomes:

```text
EV_CE
EV_PE
EV_NONE
```

The system chooses:

`CE`

if:

`CE`

is sufficiently superior and passes all hard constraints.

Likewise for:

`PE`.

Otherwise:

`NO_TRADE`.

---

# 45. E7 — Protection Experiments

This is one of the most important research layers.

We learn:

`P(MAE | State)`

`P(MFE | State)`

`P(Giveback | PeakProfit, State)`.

---

# 46. Initial Protection

The initial protection boundary is derived from:

`conditional adverse distribution`.

It is not:

`ATR × fixed number`.

---

# 47. Example

Suppose historical conditional MAE distribution gives:

```text
Q50 = ₹20
Q75 = ₹28
Q90 = ₹40
Q95 = ₹55
```

These are empirical observations.

The strategy does not automatically choose:

`₹40`.

The selection criterion determines which quantile produces the best validated economic/risk tradeoff.

---

# 48. MFE Experiment

Similarly:

`MFE`

tells us:

"Given this state, how much favorable movement is historically available?"

This helps determine whether:

`holding`

has enough continuation value to justify exposure.

---

# 49. Giveback Experiment

For every profitable historical trajectory:

measure:

`PeakProfit`

and:

`subsequentGiveback`.

Then estimate:

`P(Giveback >= g | PeakProfit, State)`.

---

# 50. Profit Floor

The profit floor becomes a conditional quantity:

```text
ProfitFloor
=
f(
    PeakProfit,
    Volatility,
    State,
    Horizon,
    Liquidity,
    ContinuationValue
)
```

It is not a fixed percentage of peak profit.

---

# 51. Protection Monotonicity

Once:

`ProfitProtectionBoundary`

moves upward for a profitable long position:

it cannot move backward merely because:

`ExpectedHorizon`

increases.

This invariant remains absolute unless the formal risk state explicitly permits another transition.

---

# 52. E8 — Execution Experiments

This determines whether the statistical opportunity is actually tradable.

We estimate:

`Spread`

`Slippage`

`FillProbability`

`Latency`

`MarketImpact`.

---

# 53. Slippage Distribution

Instead of:

`slippage = ₹X`

we estimate:

`P(Slippage | State, OrderType, Liquidity)`.

---

# 54. Latency Distribution

Likewise:

`P(ExecutionPrice | SignalTime, ExecutionTime)`.

This allows us to estimate:

`EV_after_latency`.

---

# 55. Execution Decay Curve

A particularly important experiment:

measure:

`EV(delay)`.

Conceptually:

```text
Delay
  |
  v
0 ms
10 ms
25 ms
50 ms
100 ms
250 ms
500 ms
...
```

The strategy should know how quickly its edge decays.

---

# 56. Micro-Scalping Viability

This experiment is critical for our shortest trades.

A micro signal is useful only if:

```text
ExpectedEdge
>
ExecutionCost
+
LatencyLoss
+
RiskCompensation
```

If not:

`MICRO = DISABLED`.

---

# 57. E9 — Capability Degradation Experiments

For every feature domain:

measure model performance with and without it.

For example:

`Full`

versus:

`NoDepth`.

---

# 58. Degradation Matrix

Conceptually:

```text
                 DEPTH  FLOW  IV  OPTION
FULL               Y     Y     Y     Y
NO_DEPTH           N     Y     Y     Y
NO_FLOW            Y     N     Y     Y
NO_IV              Y     Y     N     Y
PRICE_OPTION       N     N     N     Y
```

Each row becomes a separate model candidate.

---

# 59. Fallback Validation

A fallback model is active only if:

`out-of-sample validated`.

No runtime improvisation.

---

# 60. E10 — Regime Stability

Every model is evaluated across:

`volatility regimes`

`trend regimes`

`session phases`

`liquidity regimes`

`market stress`.

---

# 61. Regime Definition

Regimes are derived from historical distributions.

We do not start with arbitrary:

`low`

`medium`

`high`.

The data determines whether such segmentation is useful.

---

# 62. Regime Transition Experiment

Measure:

`P(outcome | regime transition)`.

This is particularly important for our dynamic strategy.

A trade may begin under:

`normal volatility`

and transition into:

`extreme volatility`.

The system must know how its probabilities and protection behavior should change.

---

# 63. E11 — Model Combination

Only after individual components are validated do we combine them.

For example:

```text
Probability
     +
Horizon
     +
Economic EV
     +
Execution
     +
Risk
```

The combined model is then tested again.

---

# 64. Combination Principle

A component that works individually may fail when combined because of:

`correlation`

`selection effects`

`interaction`.

Therefore:

`component validation != system validation`.

---

# 65. E12 — Final Walk-Forward

Only after all components pass their own experiments do we run the complete strategy.

The complete strategy is treated as a new model.

It receives a fresh:

`walk-forward evaluation`.

---

# 66. Complete Experiment Pipeline

```text
DATA INTEGRITY
      |
      v
FEATURE VALIDATION
      |
      v
PROBABILITY
      |
      v
HORIZON
      |
      v
ECONOMICS
      |
      v
OPTION SELECTION
      |
      v
PROTECTION
      |
      v
EXECUTION
      |
      v
CAPABILITY
      |
      v
REGIME
      |
      v
COMBINATION
      |
      v
FULL WALK-FORWARD
```

---

# 67. Experiment Independence

Experiments must not secretly reuse future information.

For example:

`E3 probability`

cannot use:

`E5 option return`

unless the latter is explicitly part of the label and is causally available only after the prediction timestamp.

---

# 68. Training/Validation/Test Ownership

For every experiment:

```text
TRAIN:
parameter estimation

VALIDATION:
parameter/model selection

TEST:
final unbiased evaluation
```

The test set does not participate in selection.

---

# 69. Purging

Because our labels can extend into the future, adjacent observations can overlap.

Therefore training observations whose label intervals overlap the validation/test interval must be removed from the training set.

Conceptually:

```text
Training label:
[10:00, 10:30]

Test begins:
10:20

=> training observation must be purged
```

---

# 70. Embargo

After a training period, an additional temporal gap may be imposed before the validation/test interval.

This reduces leakage from temporal dependence.

The embargo length becomes part of the experiment design.

It is not optimized after seeing test results.

---

# 71. Overlapping Horizon Problem

Suppose:

`Horizon = 60 minutes`.

Then many observations inside one hour are strongly dependent.

We cannot treat:

`10:00`

`10:01`

`10:02`

as three independent market experiments.

Effective sample size must account for this dependence.

---

# 72. Event Clustering

We may therefore cluster decision opportunities into market episodes.

For example:

`one signal episode`

may contain multiple ticks.

Statistical validation can operate at:

`episode level`

where appropriate.

---

# 73. Bootstrap Unit

If bootstrap analysis is used:

we should generally resample an appropriate independent unit such as:

`trade`

or:

`episode`

rather than arbitrary individual ticks.

Otherwise confidence intervals become artificially narrow.

---

# 74. Confidence Intervals

Every important performance estimate should carry uncertainty.

For example:

`ExpectedNetPnL = ₹X`

is incomplete without:

`uncertainty interval`.

---

# 75. Drawdown Distribution

Do not report only:

`maximum historical drawdown`.

Estimate the distribution of drawdown under resampling/stress assumptions.

This helps distinguish:

`observed bad luck`

from:

`structural risk`.

---

# 76. Tail Risk

We explicitly measure:

`worst trade`

`worst episode`

`loss quantiles`

`loss clustering`.

A strategy with positive average EV but catastrophic tail behavior is not automatically acceptable.

---

# 77. Stability Across Time

A parameter should be evaluated across chronological segments.

For example:

```text
Period A
Period B
Period C
Period D
Period E
```

We look for:

`sign consistency`

`magnitude stability`

`calibration stability`.

---

# 78. Stability Across Regimes

Likewise:

```text
Low volatility
Normal volatility
High volatility
Extreme volatility
```

A model can be:

`universally valid`

or:

`conditionally valid`.

Both are acceptable if explicitly represented.

---

# 79. Conditional Models

If:

`Model_A`

works in:

`low volatility`

and:

`Model_B`

works in:

`high volatility`,

we may construct:

```text
Regime detector
       |
       +--> Model A
       |
       +--> Model B
```

But the regime detector itself must be causally valid and independently validated.

---

# 80. No Endless Model Branching

We must avoid:

```text
regime
  -> subregime
      -> sub-subregime
          -> special model
              -> special exception
```

That becomes an overfitting machine.

Model complexity is itself constrained.

---

# 81. Complexity Budget

The research registry records:

`number of features`

`number of regimes`

`number of models`

`number of parameters`

`number of experiments`.

The complexity of the research process is itself evidence.

---

# 82. Simplicity Preference

If two models produce statistically indistinguishable out-of-sample performance:

prefer the simpler one.

For example:

`12 features`

should not automatically beat:

`5 features`

if their validated economic performance is equivalent.

---

# 83. Ablation Testing

For the final system:

remove one major component at a time.

Examples:

`without flow`

`without volatility`

`without horizon`

`without dynamic protection`

`without execution filter`.

Measure the effect.

---

# 84. Why Ablation Matters

Suppose the final system earns:

`₹100,000`.

Removing the probability layer changes it to:

`₹98,000`.

Then the probability layer contributes little.

Removing execution modeling changes it to:

`₹20,000`.

Then execution modeling is structurally important.

---

# 85. Component Contribution

The objective is not merely:

"does the whole thing work?"

We need:

"which components actually create the edge?"

---

# 86. Final Model Selection

The final model should maximize:

`validated economic utility`

while minimizing:

`complexity`

and:

`fragility`.

Conceptually:

```text
Utility
=
EconomicPerformance
-
RiskPenalty
-
FragilityPenalty
-
ComplexityPenalty
```

The exact penalties are defined by the validation framework.

---

# 87. Research Freeze

Once final model selection is complete:

`FEATURE_SET`

`PARAMETER_SET`

`LABELS`

`MODEL`

`EXECUTION_ASSUMPTIONS`

are frozen.

Then:

`FINAL TEST`

is executed.

---

# 88. Final Test

The final test is not:

"another validation set."

It is the closest thing we have to:

`unknown future`.

No parameter modification is allowed after observing it.

---

# 89. Failure Rule

If the final test fails:

we do not immediately tweak the model.

Instead:

`MODEL_REJECTED`.

A new research cycle begins.

Otherwise we risk:

`test -> tweak -> retest -> tweak`

until we manufacture a positive result.

---

# 90. Production Readiness

Production readiness requires:

`synthetic PASS`

+

`historical PASS`

+

`walk-forward PASS`

+

`execution PASS`

+

`stress PASS`

+

`final test PASS`.

---

# 91. First Production Model

The first production model should deliberately remain:

`simple`

`statistical`

`auditable`

`versioned`

`causal`.

No neural network.

No reinforcement learning.

No LLM decision layer.

No autonomous parameter mutation.

---

# 92. Runtime Versus Research

This distinction is now absolute:

```text
RESEARCH
--------
learn parameters
discover distributions
test hypotheses
reject models
promote models


RUNTIME
-------
consume events
update state
calculate validated features
select validated model
calculate probability
calculate economics
manage risk
execute
```

Runtime does not invent new mathematics.

---

# 93. The Resulting Architecture

```text
                    HISTORICAL DATA
                           |
                           v
                    DATA VALIDATION
                           |
                           v
                   CAUSAL RECONSTRUCTION
                           |
                           v
                  EXPERIMENTAL DATASET
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
      Probability       Horizon         Economics
          |                |                |
          +----------------+----------------+
                           |
                           v
                    Option Selection
                           |
                           v
                      Protection
                           |
                           v
                      Execution
                           |
                           v
                    Capability Models
                           |
                           v
                    Regime Validation
                           |
                           v
                   FULL WALK-FORWARD
                           |
                           v
                    FINAL TEST
                           |
                           v
                    MODEL PROMOTION
                           |
                           v
                  PRODUCTION RUNTIME
```

---

# 94. Current Architectural Status

We now have:

`Mathematical specification`

`Variable registry`

`Dependency graph`

`Temporal state machine`

`Historical label specification`

`Capability/degradation specification`

`Adversarial verification`

`Parameter-learning specification`

`Historical experiment matrix`.

The remaining major research boundary is now much narrower.

---

# 95. Next Artifact

The next artifact should be:

# WALK-FORWARD WINDOW AND PURGE/EMBARGO SPECIFICATION

This is where we stop speaking conceptually about "walk-forward" and mathematically define the actual chronology.

We need to determine:

`How much history is used for each training window`

`How validation is separated`

`How test windows move`

`How overlapping labels are purged`

`How much embargo is required`

`How many independent walk-forward folds are required`

`How model versions are promoted`

`How parameter drift is measured`

and:

`What constitutes genuine out-of-sample evidence`.

That will give us the exact temporal skeleton on which every experiment will run.