# WALK-FORWARD WINDOW, PURGE AND EMBARGO SPECIFICATION
## Canonical Temporal Validation Contract — Version 1.0

## 1. Objective

The purpose of this specification is to guarantee that every historical decision is evaluated exactly as it could have been evaluated in real time.

The fundamental temporal invariant is:

```text
At decision time t:

MODEL_t
may depend only on information available before t.

It may NOT depend on:

future observations
future labels
future parameter estimates
future model performance
future market regimes
future execution outcomes.
```

---

# 2. The Fundamental Timeline

Every experiment operates on:

```text
TRAIN -> VALIDATION -> EMBARGO -> TEST
```

Then:

```text
TEST
  |
  v
MODEL PROMOTION DECISION
  |
  v
WINDOW ADVANCES
  |
  v
NEW TRAIN -> VALIDATION -> EMBARGO -> TEST
```

There is never backward movement of information.

---

# 3. Four Distinct Time Intervals

For every walk-forward fold:

`T_train`

`T_validation`

`T_embargo`

`T_test`

These intervals must be explicitly recorded.

---

# 4. Training Interval

Training contains observations used to estimate:

`probability distributions`

`conditional distributions`

`model parameters`

`calibration`

`feature relationships`.

Nothing from:

`validation`

or:

`test`

may influence these estimates.

---

# 5. Validation Interval

Validation is used for:

`parameter selection`

`feature selection`

`model selection`

`threshold selection`

`hyperparameter selection`.

Validation is therefore not unbiased evidence of final performance.

It is part of the research process.

---

# 6. Embargo Interval

The embargo is a period immediately before the test interval during which training/validation observations that could still be statistically connected to the test outcome are excluded.

Conceptually:

```text
TRAIN | VALIDATE | EMBARGO | TEST
```

The embargo exists because temporal dependence can survive beyond the explicit label horizon.

---

# 7. Test Interval

The test interval is:

`unseen`

before the model is frozen.

The model entering the test interval is immutable.

No:

`parameter`

`feature`

`threshold`

or:

`model-selection`

decision may be changed using test results.

---

# 8. Test Is Not Validation

This distinction is absolute.

Validation asks:

"Which candidate should we choose?"

Test asks:

"How does the already-frozen candidate perform on unseen data?"

---

# 9. Why Simple Date Splitting Is Insufficient

Suppose:

```text
Training:
January 1 -> June 30

Test:
July 1 -> July 31
```

and the label horizon is:

`60 minutes`.

A training observation at:

`June 30, 23:45`

could have an outcome extending into:

`July 1`.

Therefore the training observation overlaps the test interval.

It must be purged.

---

# 10. Label Interval

Every observation has:

`decision time t`

and:

`label maturity time τ_t`.

Define:

```text
LabelInterval_t = [t, τ_t]
```

For a fixed horizon:

```text
τ_t = t + H
```

For event-dependent labels:

`τ_t`

is the actual maturity timestamp.

---

# 11. Purging Rule

For test interval:

`[T_test_start, T_test_end]`

an observation is forbidden from training if:

```text
LabelInterval_t ∩ TestInterval != ∅
```

In other words:

```text
τ_t >= T_test_start
AND
t <= T_test_end
```

means the observation must not participate in training for that test.

---

# 12. Validation Purging

The same principle applies between:

`training`

and:

`validation`.

If a training label extends into validation:

the training observation is removed.

---

# 13. Purging Is Based on Labels

Purging is not based merely on:

`feature timestamp`.

It is based on:

`future information consumed by the label`.

This distinction is important.

---

# 14. Example

Suppose:

`Training ends = 10:00`

`Validation begins = 10:30`

Maximum label horizon:

`60 minutes`.

An observation at:

`09:45`

has label interval:

`09:45 -> 10:45`.

Because:

`10:45 > 10:30`

the observation overlaps validation.

Therefore:

`09:45 observation = PURGED`.

---

# 15. Maximum Label Horizon

Define:

`H_max`.

This is the maximum future interval used by any label in the experiment.

It is not necessarily the maximum possible trade duration.

It is the maximum horizon actually consumed by the particular experiment.

---

# 16. Experiment-Specific Purging

Different experiments may have different:

`H_max`.

For example:

`micro probability`

may use a short horizon.

`intraday continuation`

may use a much longer horizon.

Therefore purge length is:

`experiment-specific`.

---

# 17. Embargo Is Different

Purging removes observations whose labels overlap the boundary.

Embargo creates an additional exclusion interval.

Therefore:

```text
PURGE:
remove overlapping labels

EMBARGO:
remove observations near the boundary
even if their labels do not directly overlap
```

---

# 18. Why Embargo Exists

Suppose two observations are:

`10:00`

and:

`10:01`.

Their labels may not technically overlap under a short horizon.

But their market states may be highly correlated.

An embargo reduces this temporal dependence.

---

# 19. Embargo Must Not Be Arbitrary

We do not declare:

`embargo = 30 minutes`

because it sounds reasonable.

It must be justified by:

`label horizon`

`serial dependence`

`feature lookback`

`market episode duration`.

---

# 20. Lookback Dependency

Suppose a feature uses:

`rolling volatility over L minutes`.

A decision at:

`10:00`

uses information back to:

`09:30`.

This is legitimate.

But the research system must record:

`FeatureLookback = 30 minutes`.

---

# 21. Feature Lookback Does Not Cause Future Leakage

A feature can legitimately consume:

```text
[t - L, t]
```

because all of that information existed by:

`t`.

The problem occurs only when it consumes:

```text
(t, future]
```

---

# 22. Training Boundary Condition

Suppose validation begins at:

`10:00`.

A training observation at:

`09:59`

can use historical information back to:

`09:00`.

That is fine.

But if its label extends into:

`10:30`,

it must be purged.

---

# 23. Maximum Dependency Horizon

Each experiment therefore records:

```text
H_feature
H_label
H_serial
```

These represent:

`feature lookback`

`future label horizon`

`temporal dependence`.

---

# 24. Temporal Isolation Requirement

For each test observation:

the model must be constructed from information that existed before the test observation.

This includes:

`feature definitions`

`feature scaling`

`normalization`

`probability calibration`

`parameter estimation`

`regime definitions`.

---

# 25. Scaling Leakage

Suppose we standardize a feature using:

`mean(all historical data)`.

That includes future information.

Invalid.

Instead:

```text
mean_t
=
mean(training observations available before t)
```

and:

```text
std_t
=
std(training observations available before t)
```

---

# 26. Distribution Leakage

The same rule applies to empirical distributions.

At time:

`t`:

```text
Distribution_t
=
distribution(
historical observations available before t
)
```

Never:

```text
distribution(all years)
```

when evaluating an earlier historical period.

---

# 27. Regime Boundary Leakage

Suppose volatility regimes are defined using the full dataset.

That could allow future volatility information to influence historical regime classification.

Therefore:

`RegimeModel_t`

must itself be trained only on information available before `t`.

---

# 28. Feature Selection Leakage

Suppose we discover after looking at the entire historical period:

"flow imbalance is the best feature."

Then use it in the backtest.

Invalid.

Feature selection belongs inside:

`TRAIN -> VALIDATION`.

The test interval remains untouched.

---

# 29. Model Selection Leakage

Suppose:

`Model A`

and:

`Model B`

are evaluated on the test set.

We select whichever wins.

The test set has now become validation.

Invalid.

---

# 30. Walk-Forward Fold

Each fold therefore contains:

```text
TRAIN
    |
    v
ESTIMATE
    |
    v
VALIDATE
    |
    v
SELECT
    |
    v
FREEZE
    |
    v
EMBARGO
    |
    v
TEST
    |
    v
RECORD
```

---

# 31. Model Freeze Point

The model is frozen at:

`T_freeze`.

After:

`T_freeze`

the following cannot change for that fold:

`feature set`

`parameters`

`probability mapping`

`horizon mapping`

`option selection rules`

`risk parameters`

`execution assumptions`.

---

# 32. Test Execution

The frozen model is then exposed sequentially to:

`T_test_start -> T_test_end`.

At each test timestamp:

```text
State_t
+
FrozenModel
->
Decision_t
```

---

# 33. No Batch Knowledge

Even though the entire test dataset exists physically in memory/storage:

the test model cannot inspect future test events.

The test engine must process:

`event by event`.

---

# 34. Test-Time State

At:

`t`

the model may use:

`state <= t`.

It cannot use:

`state > t`.

---

# 35. Test-Time Learning

Default rule:

`NO PARAMETER LEARNING`.

The test model remains frozen.

Runtime state variables may change.

Model parameters do not.

---

# 36. Runtime State Versus Parameters

For example:

`CurrentVolatility`

can change every event.

But:

`VolatilityProbabilityMapping`

does not change during the test fold.

This is the critical distinction between:

`state adaptation`

and:

`model adaptation`.

---

# 37. Walk-Forward Advancement

After a test fold completes:

the timeline advances.

The previously unseen test period may now become historical information for the next fold.

This is legitimate.

Conceptually:

```text
Fold 1:
TRAIN -> VALIDATE -> TEST1

Fold 2:
TRAIN + permitted historical information
          ->
VALIDATE2
          ->
TEST2
```

---

# 38. Expanding Window

Under an expanding design:

```text
Fold 1:
[A] -> [B] -> [C]

Fold 2:
[A+B] -> [C] -> [D]

Fold 3:
[A+B+C] -> [D] -> [E]
```

More history becomes available over time.

---

# 39. Rolling Window

Under a rolling design:

```text
Fold 1:
[A] -> [B] -> [C]

Fold 2:
[B] -> [C] -> [D]

Fold 3:
[C] -> [D] -> [E]
```

Old history is discarded.

---

# 40. Adaptive History

The strategy can eventually choose between:

`expanding`

and:

`rolling`

only through historical validation.

The choice itself becomes a model parameter.

---

# 41. History Half-Life

Instead of choosing a hard window immediately, we can estimate:

`information decay`.

Conceptually:

```text
Weight(age)
```

can be estimated from predictive usefulness.

But this function must be validated.

---

# 42. No Arbitrary Recency Constant

We do not begin with:

`λ = 0.99`.

We determine whether recency weighting provides genuine out-of-sample benefit.

If not:

`uniform weighting`

may be preferable.

---

# 43. Walk-Forward Fold Independence

The test results from previous folds must not be used to tune the next model if those results are being treated as an unbiased aggregate evaluation.

This creates an important distinction.

---

# 44. Research Mode Versus Final Evaluation Mode

During research:

previous fold outcomes may legitimately inform the next training cycle because they are now historical.

But after the final research protocol is frozen:

the aggregate final test must remain untouched.

---

# 45. Final Evaluation

We ultimately want:

```text
MODEL DESIGN
     |
     v
ALL RESEARCH DECISIONS FROZEN
     |
     v
FINAL UNTOUCHED WALK-FORWARD PERIOD
```

This produces the strongest evidence.

---

# 46. Number of Folds

We do not define:

`10 folds`

because ten sounds statistically sufficient.

The number must provide:

`multiple independent market regimes`

and:

`sufficient test observations`.

---

# 47. Fold Size

Fold duration must balance:

`statistical sample size`

against:

`regime stability`.

Very short folds produce:

`high variance`.

Very long folds may hide:

`parameter drift`.

---

# 48. Fold Design Experiment

Candidate designs can be evaluated during research.

For example:

```text
Short training / short test
Medium training / medium test
Long training / short test
Long training / long test
```

But the final choice is frozen before final evaluation.

---

# 49. Parameter Drift

For every learned parameter:

track:

`θ_1`

`θ_2`

`θ_3`

...

across walk-forward folds.

---

# 50. Drift Metric

A parameter can have:

`absolute drift`

and:

`relative drift`.

For example:

```text
Drift_t
=
|θ_t - θ_(t-1)|
```

and:

```text
RelativeDrift_t
=
|θ_t - θ_(t-1)| / |θ_(t-1)|
```

---

# 51. Why Drift Matters

If:

`ProfitFloorQuantile`

moves:

`0.20 -> 0.21 -> 0.19 -> 0.22`

that may represent normal statistical variation.

If it moves:

`0.20 -> 0.85 -> 0.05 -> 0.92`

the model is unstable.

---

# 52. Parameter Stability Distribution

We therefore measure:

`Distribution(θ_t)`.

A parameter does not need to remain numerically identical.

It needs to remain:

`statistically stable`

and:

`economically useful`.

---

# 53. Parameter Drift Does Not Automatically Mean Failure

Markets are non-stationary.

Some drift is expected.

The question is:

"Does the strategy remain robust under that drift?"

---

# 54. Parameter Drift Versus Model Failure

Two cases:

```text
Stable parameter + deteriorating performance
```

versus:

```text
Changing parameter + stable performance
```

These imply different problems.

The first may indicate:

`edge decay`.

The second may indicate:

`adaptive parameterization is working`.

---

# 55. Parameter Confidence

Each learned parameter should eventually carry:

`estimate`

plus:

`uncertainty`.

For example:

```text
θ = 0.31
CI = [0.27, 0.36]
```

The precise interval method depends on the estimator.

---

# 56. Fold-Level Confidence

Similarly:

`ExpectedNetEV`

must be measured across folds.

We care about:

`median`

`mean`

`dispersion`

`worst fold`

`fraction profitable`.

---

# 57. Worst-Fold Analysis

A model with:

`9 excellent folds`

and:

`1 catastrophic fold`

requires investigation.

The average alone is insufficient.

---

# 58. Fold Sign Consistency

For each fold:

```text
EV_fold_i
```

Record:

`sign(EV_fold_i)`.

A robust strategy should demonstrate reasonable consistency rather than relying entirely on a few positive periods.

---

# 59. Regime Coverage

The walk-forward test set should collectively contain:

`low volatility`

`normal volatility`

`high volatility`

`trend`

`range`

`opening`

`mid-session`

`late session`

and other materially distinct environments actually present in the data.

---

# 60. No Synthetic Regime Guarantee

We do not manufacture regimes merely to satisfy a checklist.

If the historical period lacks a regime:

we record:

`UNOBSERVED`.

We do not claim validation for it.

---

# 61. Test Coverage Matrix

The final research report should contain:

```text
             LOW  NORMAL HIGH EXTREME
TREND         ?      ?     ?      ?
RANGE         ?      ?     ?      ?
OPEN          ?      ?     ?      ?
MID           ?      ?     ?      ?
LATE          ?      ?     ?      ?
```

Each cell represents actual observed test evidence.

---

# 62. Data Sufficiency

A regime cell with:

`N_eff ≈ 0`

cannot produce reliable conclusions.

It is marked:

`INSUFFICIENT_SAMPLE`.

---

# 63. Test Result Aggregation

We must not simply concatenate all test trades and calculate one P&L number.

We calculate:

`per-fold metrics`

then:

`aggregate metrics`.

This preserves temporal structure.

---

# 64. Fold Weighting

A fold containing:

`10,000 trades`

should not necessarily dominate a fold containing:

`500 trades`.

Depending on the research question, we may examine:

`equal-fold weighting`

and:

`trade-weighted aggregation`.

Both should be reported where useful.

---

# 65. No Hidden Weighting

The aggregation method itself must be declared before final test analysis.

We cannot choose:

"whichever weighting makes the result look best."

---

# 66. Sequential Test Integrity

Because walk-forward test periods are sequential, they are not necessarily statistically independent.

Therefore:

`N_test_trades`

must not automatically be interpreted as:

`N independent observations`.

---

# 67. Effective Test Evidence

We therefore distinguish:

`N_trades`

`N_episodes`

`N_days`

`N_weeks`

`N_regimes`.

This gives a more honest view of evidence.

---

# 68. Daily Clustering

If hundreds of trades occur on one day, that day may dominate the apparent evidence.

We therefore analyze:

`daily P&L`

and:

`daily trade clusters`.

---

# 69. Strategy-Level Bootstrap

If bootstrap analysis is used:

resampling should respect the temporal dependency structure.

For example:

`day-level`

or:

`episode-level`

resampling may be more appropriate than independent trade resampling.

---

# 70. Catastrophic Scenario Preservation

The walk-forward process must not remove:

`bad days`

`high-volatility days`

`feed-degraded periods`

or:

`execution failures`

because they make performance unattractive.

Those periods are part of the strategy's true environment.

---

# 71. Missing Data in Test

If test data is unavailable:

we do not silently remove that period.

The period receives:

`DATA_UNAVAILABLE`.

The final report distinguishes:

`strategy failure`

from:

`data failure`.

---

# 72. Data Availability Bias

If the strategy is only evaluated on periods where data quality was excellent:

the test may become biased toward favorable conditions.

Therefore data availability itself must be reported.

---

# 73. Capability-Aware Test

Each test observation receives:

`CapabilityState`.

Performance is then segmented by:

`FULL`

`PARTIAL`

`DEGRADED`

`EXECUTION_LIMITED`.

---

# 74. Model Fallback Validation

Suppose:

`FULL_MODEL`

is active normally.

During degraded data:

`FALLBACK_MODEL`.

The test must evaluate:

`full`

and:

`fallback`

separately.

---

# 75. Fallback Promotion

A fallback model is promoted only if:

`its own walk-forward performance`

passes the same validation framework.

No fallback receives weaker standards simply because it is used during data problems.

---

# 76. Dynamic Mode Validation

The final test must also measure:

`MICRO`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`.

We need to determine whether dynamic mode selection actually improves performance over:

`single-mode baselines`.

---

# 77. Mode Ablation

Compare:

```text
Dynamic Mode
vs
Always Micro
vs
Always Scalp
vs
Always Intraday
```

under identical execution assumptions.

This is essential.

Otherwise we cannot prove that dynamic classification contributes value.

---

# 78. Dynamic Protection Ablation

Likewise compare:

```text
Dynamic Protection
vs
Static Protection
```

using the same entry signals.

This isolates the contribution of the protection architecture.

---

# 79. Combined Ablation

Then:

```text
Static Entry + Static Protection

Static Entry + Dynamic Protection

Dynamic Entry + Static Protection

Dynamic Entry + Dynamic Protection
```

This tells us exactly where the performance originates.

---

# 80. Critical Success Condition

The complete system should not merely outperform a naive baseline.

It should demonstrate that each major architectural component contributes meaningful validated value.

---

# 81. Baseline Strategies

We require simple baselines such as:

`No-trade`

`Random directional entry`

`Simple momentum`

`Simple volatility breakout`

`Static stop`

`Static target`.

The purpose is not to trade them.

The purpose is to determine whether our complexity actually buys something.

---

# 82. Complexity Justification

If:

`Complex strategy`

and:

`simple baseline`

produce statistically indistinguishable results:

prefer the simple baseline.

This is a hard research principle.

---

# 83. Parameter Drift Decision

After each walk-forward cycle:

the system records:

`parameter drift`

`performance drift`

`calibration drift`.

It does not automatically retrain merely because drift exists.

---

# 84. Retraining Trigger

A retraining trigger can eventually be defined using:

`statistical degradation`

or:

`data drift`.

But the trigger itself must be validated historically.

---

# 85. No Performance-Chasing

The system must never implement:

```text
Performance drops
    ->
change parameters
    ->
performance improves
    ->
keep parameters
```

without an independently validated retraining protocol.

That is curve fitting.

---

# 86. Research Retraining

A legitimate retraining process is:

```text
Historical data
    ->
predefined retraining schedule
    ->
new training window
    ->
new candidate
    ->
validation
    ->
promotion
```

The schedule itself is fixed before final evaluation.

---

# 87. Model Version Timeline

The production timeline becomes:

```text
MODEL V1
|----------------|
                 |
                 v
              V2
                 |----------------|
                                  |
                                  v
                               V3
```

Every timestamp belongs to exactly one active model version.

---

# 88. No Retroactive Model Replacement

If:

`V3`

is better than:

`V2`,

historical trades executed under V2 remain attributed to V2.

We never rewrite historical decisions using V3.

---

# 89. Model Registry

Each version records:

`MODEL_ID`

`TRAIN_END`

`VALIDATION_END`

`FREEZE_TIME`

`TEST_START`

`TEST_END`

`FEATURE_VERSION`

`LABEL_VERSION`

`PARAMETER_VERSION`

`DATA_VERSION`.

---

# 90. Reproducibility Requirement

Given:

`MODEL_ID`

and:

`historical event stream`

we should be able to reconstruct:

`State_t`

`Decision_t`

`Position_t`

`Exit_t`.

If we cannot reproduce a historical decision:

the research pipeline is not sufficiently controlled.

---

# 91. Final Temporal Invariant

For every historical decision:

```text
Decision_t
=
F(
    Events_<=t,
    FrozenModelVersion_t
)
```

That is the central equation.

---

# 92. Learning Equation

For a model version created at time `T`:

```text
Model_T
=
Train(
    HistoricalInformation_<T
)
```

followed by:

```text
Model_T
=
Validated(
    Model_T
)
```

Then:

```text
Model_T
```

is frozen during its test interval.

---

# 93. Promotion Equation

Conceptually:

```text
Promote(Model)
=
PASS(
    statistical_tests
    AND
    economic_tests
    AND
    execution_tests
    AND
    risk_tests
    AND
    stability_tests
)
```

If false:

`REJECT`.

---

# 94. Final Walk-Forward Architecture

```text
                 HISTORICAL EVENTS
                        |
                        v
                CAUSAL RECONSTRUCTION
                        |
                        v
               DECISION OPPORTUNITIES
                        |
                        v
              +----------------------+
              |      TRAIN WINDOW    |
              +----------------------+
                        |
                        v
                  PARAMETER FIT
                        |
                        v
              +----------------------+
              |   VALIDATION WINDOW  |
              +----------------------+
                        |
                        v
                  MODEL SELECTION
                        |
                        v
                  MODEL FREEZE
                        |
                        v
              +----------------------+
              |      EMBARGO         |
              +----------------------+
                        |
                        v
              +----------------------+
              |       TEST           |
              +----------------------+
                        |
                        v
                 RECORD RESULTS
                        |
                        v
                 ADVANCE TIME
                        |
                        v
                 NEXT WALK-FORWARD
```

---

# 95. What Is Now Frozen

The following are now architectural requirements:

`Temporal ordering`

`Label intervals`

`Purging principle`

`Embargo principle`

`Model freeze`

`Test isolation`

`Versioning`

`Reproducibility`

`No test-driven parameter changes`

`Capability-aware evaluation`

`Mode ablation`

`Protection ablation`

`Baseline comparison`.

---

# 96. What Remains Empirical

We deliberately have NOT fixed:

`Training duration`

`Validation duration`

`Test duration`

`Embargo duration`

`Recency decay`

`Minimum N_eff`

`Retraining frequency`

`Fold count`.

These are not theoretical constants.

They must be determined by historical evidence and research constraints.

---

# 97. Important Constraint

We must not optimize:

`training duration`

`validation duration`

`embargo`

`retraining frequency`

against the final test set.

Otherwise these become hidden hyperparameters.

---

# 98. Research-Phase Search

During the research phase, candidate temporal designs can be compared using:

`nested validation`.

For example:

```text
Outer:
TRAIN -> TEST

Inner:
TRAIN -> VALIDATE
```

The inner process chooses:

`window length`

`parameter values`

`model`.

The outer test remains untouched.

---

# 99. Nested Walk-Forward

Conceptually:

```text
OUTER TRAIN
    |
    +--> INNER TRAIN
    |       |
    |       v
    |    INNER VALIDATE
    |       |
    |       v
    |    SELECT
    |
    v
OUTER TEST
```

This is the rigorous mechanism for choosing the temporal architecture itself.

---

# 100. Final Principle

We now have a hierarchy:

```text
EVENT
  ->
STATE
  ->
FEATURE
  ->
LABEL
  ->
PARAMETER
  ->
MODEL
  ->
WALK-FORWARD
  ->
OUT-OF-SAMPLE EVIDENCE
```

Every layer has a temporal boundary.

Nothing above a layer may leak information backward into that layer.

---

# 101. Current Status

The strategy specification is now structurally complete enough that we can define the actual historical research protocol.

We have:

`State specification`

`Dependency DAG`

`Temporal state transitions`

`Probability mechanism`

`Economic decision mechanism`

`Dynamic mode`

`Dynamic protection`

`Data capability`

`Adversarial verification`

`Parameter-learning framework`

`Historical experiment matrix`

`Walk-forward temporal framework`.

---

# 102. Next Artifact

The next artifact should be:

# SYNTHETIC MARKET GENERATOR AND COUNTERFACTUAL VERIFICATION SPECIFICATION

Before touching real historical data, we should create mathematically controlled synthetic markets where we know the true answer.

We will construct environments such as:

`No-edge random walk`

`Known momentum edge`

`Known mean-reversion edge`

`Volatility-regime switching`

`False breakout process`

`Liquidity collapse`

`Latency-dependent edge`

`Option theta decay`

`IV shock`

`Profit-reversal process`

`Adversarial noise`.

The critical test is:

```text
If the synthetic market contains NO EDGE,
does our system correctly produce approximately NO EDGE?
```

And:

```text
If we inject a known edge,
does the system recover it?
```

That is an exceptionally powerful test.

If the system discovers a profitable strategy in a mathematically generated market where no predictive edge exists, we know immediately that our research pipeline is generating false discoveries.

Only after that passes should we trust the historical experiments.